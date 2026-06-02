import sqlite3
from datetime import datetime, timezone
from typing import Callable

from app.repositories.sqlite_repository import find_existing_thread_ids, insert_post
from app.services.summary_service import fallback_summary
from app.utils.logger import get_logger


logger = get_logger(__name__)


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
    logger.info(
        "Post diff complete: input=%s existing=%s new=%s board_type=%s",
        len(posts),
        len(existing_ids),
        len(new_posts),
        board_type,
    )

    now = datetime.now(timezone.utc).isoformat()
    for post in new_posts:
        post_to_insert = dict(post)
        if detail_body_fetcher is not None:
            post_to_insert["detail_body"] = _fetch_detail_body(
                detail_body_fetcher,
                post,
            )
        if summary_generator is not None:
            detail_body = str(post_to_insert.get("detail_body", ""))
            if detail_body.strip():
                post_to_insert["summary_text"] = _generate_summary(
                    summary_generator,
                    post_to_insert,
                )
            else:
                logger.debug(
                    "Skipping summary generation because detail body is empty: thread_id=%s",
                    post["thread_id"],
                )
                post_to_insert["summary_text"] = fallback_summary("")

        logger.debug(
            "Inserting new post thread_id=%s board_type=%s",
            post["thread_id"],
            board_type,
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
    thread_id = post["thread_id"]
    logger.debug("Fetching detail body for thread_id=%s", thread_id)
    try:
        detail_body = detail_body_fetcher(post["url"])
        logger.debug(
            "Detail body fetched for thread_id=%s chars=%s",
            thread_id,
            len(detail_body),
        )
        return detail_body
    except Exception as exc:
        logger.warning(
            "Notice detail body fetch failed for thread_id=%s: %s",
            thread_id,
            exc,
        )
        return ""


def _generate_summary(
    summary_generator: Callable[[dict], str],
    post: dict,
) -> str:
    thread_id = post["thread_id"]
    logger.debug("Generating summary for thread_id=%s", thread_id)
    try:
        summary_text = summary_generator(post)
        logger.debug(
            "Summary generated for thread_id=%s chars=%s",
            thread_id,
            len(summary_text),
        )
        return summary_text
    except Exception as exc:
        logger.warning(
            "Notice summary generation failed for thread_id=%s: %s",
            thread_id,
            exc,
        )
        # Summary generation is one-shot for storage; fallback keeps Discord messages useful.
        return fallback_summary(post.get("detail_body", ""))
