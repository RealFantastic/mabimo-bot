import sqlite3
from datetime import datetime, timezone

from app.repositories.sqlite_repository import find_existing_thread_ids, insert_post
from app.utils.logger import get_logger


logger = get_logger(__name__)


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
    logger.info(
        "Post diff complete: input=%s existing=%s new=%s board_type=%s",
        len(posts),
        len(existing_ids),
        len(new_posts),
        board_type,
    )

    now = datetime.now(timezone.utc).isoformat()
    for post in new_posts:
        logger.debug(
            "Inserting new post thread_id=%s board_type=%s",
            post["thread_id"],
            board_type,
        )
        insert_post(
            connection,
            post,
            board_type=board_type,
            first_seen_at=now,
        )

    return new_posts
