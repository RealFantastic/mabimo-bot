import sqlite3
from datetime import datetime, timezone

from app.repositories.sqlite_repository import find_existing_thread_ids, insert_post


def detect_and_store_new_posts(
    connection: sqlite3.Connection,
    posts: list[dict],
    *,
    board_type: str,
) -> list[dict]:
    existing_ids = find_existing_thread_ids(
        connection, (post["thread_id"] for post in posts)
    )
    new_posts = [post for post in posts if post["thread_id"] not in existing_ids]

    now = datetime.now(timezone.utc).isoformat()
    for post in new_posts:
        insert_post(
            connection,
            post,
            board_type=board_type,
            first_seen_at=now,
        )

    return new_posts
