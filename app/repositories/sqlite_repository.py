import os
import sqlite3
from pathlib import Path
from typing import Iterable

from app.utils.logger import get_logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "mabimo.db"
logger = get_logger(__name__)


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    resolved_db_path = Path(os.getenv("MABIMO_DB_PATH") or db_path or DEFAULT_DB_PATH)
    logger.debug("Opening SQLite database at %s", resolved_db_path)
    connection = sqlite3.connect(resolved_db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    logger.info("Initializing SQLite schema")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            thread_id TEXT PRIMARY KEY,
            board_type TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            published_at TEXT,
            url TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            notified_at TEXT
        )
        """
    )
    # notification_deliveries records each notification send attempt without a
    # strong posts FK because test sends may not map to a real post.
    #
    # Columns:
    # - id: local delivery row identifier.
    # - notification_type: delivery reason; expected values are new_post, updated_post, test.
    # - channel_type: messenger channel; expected values are discord, slack, kakaotalk.
    # - status: send lifecycle state; expected values are pending, sent, failed, skipped.
    # - board_type: optional board identity for real post notifications; NULL for test sends.
    # - thread_id: optional post thread identity; NULL for test sends.
    # - title: optional notification title snapshot for delivery logs.
    # - url: optional target URL snapshot for delivery logs.
    # - message: rendered notification body snapshot for delivery logs.
    # - attempt_count: number of send attempts recorded for this delivery.
    # - created_at: row creation timestamp.
    # - last_attempt_at: timestamp of the latest send attempt.
    # - sent_at: timestamp of successful send completion.
    # - error_message: latest send failure detail, if any.
    # - response_status_code: latest channel response status code, if available.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL CHECK (
                notification_type IN ('new_post', 'updated_post', 'test')
            ),
            channel_type TEXT NOT NULL CHECK (
                channel_type IN ('discord', 'slack', 'kakaotalk')
            ),
            status TEXT NOT NULL DEFAULT 'pending' CHECK (
                status IN ('pending', 'sent', 'failed', 'skipped')
            ),
            board_type TEXT,
            thread_id TEXT,
            title TEXT,
            url TEXT,
            message TEXT NOT NULL DEFAULT '',
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_attempt_at TEXT,
            sent_at TEXT,
            error_message TEXT,
            response_status_code INTEGER
        )
        """
    )
    connection.commit()
    logger.info("SQLite schema initialization complete")


def find_existing_thread_ids(
    connection: sqlite3.Connection, thread_ids: Iterable[str]
) -> set[str]:
    ids = list(thread_ids)
    if not ids:
        logger.debug("Existing thread ID lookup skipped because input is empty")
        return set()

    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"SELECT thread_id FROM posts WHERE thread_id IN ({placeholders})",
        ids,
    ).fetchall()
    existing_ids = {row["thread_id"] for row in rows}
    logger.debug(
        "Existing thread ID lookup complete: requested=%s matched=%s",
        len(ids),
        len(existing_ids),
    )
    return existing_ids


def insert_post(
    connection: sqlite3.Connection,
    post: dict,
    *,
    board_type: str,
    first_seen_at: str,
) -> None:
    logger.debug(
        "Inserting post row: thread_id=%s board_type=%s",
        post["thread_id"],
        board_type,
    )
    connection.execute(
        """
        INSERT INTO posts (
            thread_id,
            board_type,
            title,
            category,
            published_at,
            url,
            first_seen_at,
            notified_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            post["thread_id"],
            board_type,
            post["title"],
            post.get("category", ""),
            post.get("published_at", ""),
            post["url"],
            first_seen_at,
        ),
    )
    connection.commit()
    logger.info("Inserted post row: thread_id=%s", post["thread_id"])


def update_notified_at(
    connection: sqlite3.Connection, thread_id: str, notified_at: str
) -> None:
    # notified_at is written only after a successful send; NULL means retryable pending work.
    cursor = connection.execute(
        "UPDATE posts SET notified_at = ? WHERE thread_id = ?",
        (notified_at, thread_id),
    )
    connection.commit()
    logger.info(
        "Updated notified_at: thread_id=%s rows=%s",
        thread_id,
        cursor.rowcount,
    )


def find_pending_notifications(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT
            thread_id,
            board_type,
            title,
            category,
            published_at,
            url,
            first_seen_at,
            notified_at
        FROM posts
        WHERE notified_at IS NULL
        ORDER BY first_seen_at ASC
        """
    ).fetchall()
    pending = [dict(row) for row in rows]
    logger.debug("Pending notification query complete: count=%s", len(pending))
    return pending
