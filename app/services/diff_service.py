import sqlite3
from datetime import datetime, timezone
from typing import Callable

from app.repositories.sqlite_repository import find_existing_thread_ids, insert_post
from app.services.summary_service import fallback_summary


def detect_and_store_new_posts(
    connection: sqlite3.Connection,
    posts: list[dict],
    *,
    board_type: str,
    detail_body_fetcher: Callable[[str], str] | None = None,
    summary_generator: Callable[[dict], str] | None = None,
) -> list[dict]:
    existing_ids = find_existing_thread_ids(
        connection, (post["thread_id"] for post in posts)
    )
    new_posts = [post for post in posts if post["thread_id"] not in existing_ids]

    now = datetime.now(timezone.utc).isoformat()
    for post in new_posts:
        post_to_insert = dict(post)
        if detail_body_fetcher is not None:
            post_to_insert["detail_body"] = _fetch_detail_body(
                detail_body_fetcher,
                post,
            )
        if summary_generator is not None:
            post_to_insert["summary_text"] = _generate_summary(
                summary_generator,
                post_to_insert,
            )

        insert_post(
            connection,
            post_to_insert,
            board_type=board_type,
            first_seen_at=now,
        )

    return new_posts


def _fetch_detail_body(
    detail_body_fetcher: Callable[[str], str],
    post: dict,
) -> str:
    try:
        return detail_body_fetcher(post["url"])
    except Exception as exc:
        print(f"[WARNING] Notice detail body fetch failed for {post['thread_id']}: {exc}")
        return ""


def _generate_summary(
    summary_generator: Callable[[dict], str],
    post: dict,
) -> str:
    try:
        return summary_generator(post)
    except Exception as exc:
        print(f"[WARNING] Notice summary generation failed for {post['thread_id']}: {exc}")
        return fallback_summary(post.get("detail_body", ""))
