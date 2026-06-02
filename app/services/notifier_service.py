import httpx
import time

from app.services.summary_service import fallback_summary


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
        summary_text = fallback_summary(post.get("detail_body", ""))

    return (
        f"📢 [공지사항] {post['title']}\n\n"
        f"{summary_text}\n\n"
        f"🔗 원문: {post['url']}"
    )


def send_discord_notification(webhook_url: str, post: dict) -> None:
    message = format_notice_message(post)
    payload = {
        "content": message,
        "allowed_mentions": {"parse": []},
    }

    for attempt in range(2):
        try:
            response = httpx.post(
                webhook_url,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            return
        except httpx.HTTPStatusError as exc:
            response = exc.response
            if response.status_code == 429 and attempt == 0:
                time.sleep(min(_retry_after_seconds(response), 30.0))
                continue

            raise DiscordNotificationError(
                f"Discord webhook returned HTTP {response.status_code}",
                status_code=response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise DiscordNotificationError(
                f"Discord webhook request failed: {exc.__class__.__name__}"
            ) from exc
