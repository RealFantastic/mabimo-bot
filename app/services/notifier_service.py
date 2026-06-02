import httpx
import time

from app.services.summary_service import fallback_summary
from app.utils.logger import get_logger


logger = get_logger(__name__)
DISCORD_CONTENT_LIMIT = 2000


class DiscordNotificationError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _retry_after_seconds(response: httpx.Response) -> float:
    try:
        data = response.json()
        retry_after = data.get("retry_after")
        if retry_after is not None:
            return float(retry_after)
    except (ValueError, TypeError):
        pass

    retry_after_header = response.headers.get("Retry-After")
    if retry_after_header:
        try:
            return float(retry_after_header)
        except ValueError:
            pass

    return 1.0


def format_notice_message(post: dict) -> str:
    summary_text = post.get("summary_text", "").strip()
    if not summary_text:
        logger.debug(
            "Formatting notice message with fallback summary: thread_id=%s",
            post["thread_id"],
        )
        summary_text = fallback_summary(post.get("detail_body", ""))

    title_line = f"📢 [공지사항] {post['title']}"
    url_line = f"🔗 원문: {post['url']}"
    return _format_with_content_limit(
        title_line=title_line,
        body=summary_text,
        url_line=url_line,
    )


def _format_with_content_limit(*, title_line: str, body: str, url_line: str) -> str:
    body_budget = DISCORD_CONTENT_LIMIT - len(title_line) - len(url_line) - 4
    if body_budget >= 0:
        return f"{title_line}\n\n{body[:body_budget]}\n\n{url_line}"

    title_budget = DISCORD_CONTENT_LIMIT - len(url_line) - 2
    if title_budget > 0:
        return f"{title_line[:title_budget]}\n\n{url_line}"

    return url_line[:DISCORD_CONTENT_LIMIT]


def send_discord_notification(webhook_url: str, post: dict) -> None:
    message = format_notice_message(post)
    thread_id = post["thread_id"]
    logger.debug(
        "Formatted notice message: thread_id=%s chars=%s",
        thread_id,
        len(message),
    )
    payload = {
        "content": message,
        # Prevent notice text from accidentally pinging Discord users or roles.
        "allowed_mentions": {"parse": []},
    }

    for attempt in range(2):
        logger.debug(
            "Sending Discord notification: thread_id=%s attempt=%s",
            thread_id,
            attempt + 1,
        )
        try:
            response = httpx.post(
                webhook_url,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info(
                "Discord notification sent: thread_id=%s status_code=%s",
                thread_id,
                response.status_code,
            )
            return
        except httpx.HTTPStatusError as exc:
            response = exc.response
            if response.status_code == 429 and attempt == 0:
                retry_after = min(_retry_after_seconds(response), 30.0)
                logger.warning(
                    "Discord rate limit hit: thread_id=%s retry_after_seconds=%s",
                    thread_id,
                    retry_after,
                )
                time.sleep(retry_after)
                continue

            logger.error(
                "Discord webhook HTTP error: thread_id=%s status_code=%s",
                thread_id,
                response.status_code,
            )
            raise DiscordNotificationError(
                f"Discord webhook returned HTTP {response.status_code}",
                status_code=response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "Discord webhook request error: thread_id=%s error_type=%s",
                thread_id,
                exc.__class__.__name__,
            )
            raise DiscordNotificationError(
                f"Discord webhook request failed: {exc.__class__.__name__}"
            ) from exc
