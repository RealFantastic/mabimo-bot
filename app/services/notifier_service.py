import httpx
import time

from app.utils.logger import get_logger


logger = get_logger(__name__)
DISCORD_CONTENT_LIMIT = 2000
BOARD_LABELS = {
    "notice": "공지사항",
    "update": "업데이트",
    "event": "이벤트",
    "known_issue": "확인 중인 문제",
}


class DiscordNotificationError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UnknownBoardTypeError(ValueError):
    pass


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
    title_line = f"📢 [공지사항] {post['title']}"
    category_line = f"분류: {post.get('category', '')}"
    published_at_line = f"작성일: {post.get('published_at', '')}"
    url_line = f"🔗 원문: {post['url']}"
    return _format_with_content_limit(
        title_line=title_line,
        metadata_lines=[category_line, published_at_line],
        url_line=url_line,
    )


def format_post_message(post: dict) -> str:
    board_type = post.get("board_type")
    try:
        label = BOARD_LABELS[board_type]
    except KeyError as exc:
        raise UnknownBoardTypeError(f"Unknown board_type: {board_type}") from exc

    title_line = f"[{label}] {post['title']}"
    category_line = f"분류: {post.get('category', '')}"
    published_at_line = f"작성일: {post.get('published_at', '')}"
    url_line = f"링크: {post['url']}"
    return _format_with_content_limit(
        title_line=title_line,
        metadata_lines=[category_line, published_at_line],
        url_line=url_line,
    )


def _format_with_content_limit(
    *,
    title_line: str,
    metadata_lines: list[str],
    url_line: str,
) -> str:
    message = "\n".join([title_line, "", *metadata_lines, url_line])
    if len(message) <= DISCORD_CONTENT_LIMIT:
        return message

    title_budget = DISCORD_CONTENT_LIMIT - len(url_line) - 2
    if title_budget > 0:
        return f"{title_line[:title_budget]}\n\n{url_line}"

    return url_line[:DISCORD_CONTENT_LIMIT]


def send_discord_notification(webhook_url: str, post: dict) -> None:
    message_post = post if post.get("board_type") else {**post, "board_type": "notice"}
    message = format_post_message(message_post)
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
