import httpx


def format_notice_message(post: dict) -> str:
    return (
        "[공지사항]\n\n"
        f"제목: {post['title']}\n"
        f"분류: {post.get('category', '')}\n"
        f"작성일: {post.get('published_at', '')}\n"
        f"링크: {post['url']}"
    )


def send_discord_notification(webhook_url: str, post: dict) -> None:
    message = format_notice_message(post)
    response = httpx.post(
        webhook_url,
        json={"content": message},
        timeout=10.0,
    )
    response.raise_for_status()
