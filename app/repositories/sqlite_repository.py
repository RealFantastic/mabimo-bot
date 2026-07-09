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
    _create_posts_table(connection)
    _migrate_posts_to_board_thread_identity(connection)
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
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            ux_notification_deliveries_real_post
        ON notification_deliveries (
            notification_type,
            channel_type,
            board_type,
            thread_id
        )
        WHERE board_type IS NOT NULL
            AND thread_id IS NOT NULL
        """
    )
    _backfill_legacy_post_notifications(connection)
    connection.commit()
    logger.info("SQLite schema initialization complete")


def _create_posts_table(
    connection: sqlite3.Connection, *, include_notified_at: bool = False
) -> None:
    notified_at_column = ",\n            notified_at TEXT" if include_notified_at else ""
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS posts (
            thread_id TEXT NOT NULL,
            board_type TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            published_at TEXT,
            url TEXT NOT NULL,
            first_seen_at TEXT NOT NULL{notified_at_column},
            PRIMARY KEY (board_type, thread_id)
        )
        """
    )


def _posts_columns(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute("PRAGMA table_info(posts)").fetchall()


def _posts_has_board_thread_primary_key(connection: sqlite3.Connection) -> bool:
    primary_key_columns = sorted(
        ((row["pk"], row["name"]) for row in _posts_columns(connection) if row["pk"]),
        key=lambda item: item[0],
    )
    return primary_key_columns == [(1, "board_type"), (2, "thread_id")]


def _migrate_posts_to_board_thread_identity(connection: sqlite3.Connection) -> None:
    if _posts_has_board_thread_primary_key(connection):
        return

    columns = _posts_columns(connection)
    column_names = {row["name"] for row in columns}
    include_notified_at = "notified_at" in column_names
    logger.info("Migrating posts schema to board-aware identity")

    connection.execute("ALTER TABLE posts RENAME TO posts_legacy_thread_id_identity")
    _create_posts_table(connection, include_notified_at=include_notified_at)

    insert_columns = [
        "thread_id",
        "board_type",
        "title",
        "category",
        "published_at",
        "url",
        "first_seen_at",
    ]
    if include_notified_at:
        insert_columns.append("notified_at")

    columns_sql = ", ".join(insert_columns)
    connection.execute(
        f"""
        INSERT OR IGNORE INTO posts ({columns_sql})
        SELECT {columns_sql}
        FROM posts_legacy_thread_id_identity
        """
    )
    connection.execute("DROP TABLE posts_legacy_thread_id_identity")


def _posts_has_notified_at(connection: sqlite3.Connection) -> bool:
    columns = _posts_columns(connection)
    return any(row["name"] == "notified_at" for row in columns)


def _backfill_legacy_post_notifications(connection: sqlite3.Connection) -> None:
    if not _posts_has_notified_at(connection):
        return

    logger.info("Backfilling legacy posts.notified_at into notification_deliveries")
    connection.execute(
        """
        INSERT OR IGNORE INTO notification_deliveries (
            notification_type,
            channel_type,
            status,
            board_type,
            thread_id,
            title,
            url,
            attempt_count,
            last_attempt_at,
            sent_at
        )
        SELECT
            'new_post',
            'discord',
            CASE WHEN notified_at IS NULL THEN 'pending' ELSE 'sent' END,
            board_type,
            thread_id,
            title,
            url,
            CASE WHEN notified_at IS NULL THEN 0 ELSE 1 END,
            notified_at,
            notified_at
        FROM posts
        """
    )


def find_existing_thread_ids(
    connection: sqlite3.Connection, thread_ids: Iterable[str], *, board_type: str
) -> set[str]:
    ids = list(thread_ids)
    if not ids:
        logger.debug("Existing thread ID lookup skipped because input is empty")
        return set()

    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT thread_id
        FROM posts
        WHERE board_type = ?
            AND thread_id IN ({placeholders})
        """,
        [board_type, *ids],
    ).fetchall()
    existing_ids = {row["thread_id"] for row in rows}
    logger.debug(
        "Existing thread ID lookup complete: requested=%s matched=%s board_type=%s",
        len(ids),
        len(existing_ids),
        board_type,
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
            first_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
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
    create_pending_delivery(connection, post, board_type=board_type, commit=False)
    connection.commit()
    logger.info("Inserted post row: thread_id=%s", post["thread_id"])


def create_pending_delivery(
    connection: sqlite3.Connection,
    post: dict,
    *,
    board_type: str,
    commit: bool = True,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO notification_deliveries (
            notification_type,
            channel_type,
            status,
            board_type,
            thread_id,
            title,
            url
        )
        VALUES ('new_post', 'discord', 'pending', ?, ?, ?, ?)
        """,
        (
            board_type,
            post["thread_id"],
            post["title"],
            post["url"],
        ),
    )
    if commit:
        connection.commit()


def create_test_delivery(connection: sqlite3.Connection, *, message: str) -> int:
    cursor = connection.execute(
        """
        INSERT INTO notification_deliveries (
            notification_type,
            channel_type,
            status,
            message
        )
        VALUES ('test', 'discord', 'pending', ?)
        """,
        (message,),
    )
    connection.commit()
    delivery_id = int(cursor.lastrowid)
    logger.info("Created test delivery: delivery_id=%s", delivery_id)
    return delivery_id


def mark_delivery_sent(
    connection: sqlite3.Connection,
    delivery_id: int,
    *,
    sent_at: str,
    response_status_code: int | None = None,
) -> None:
    cursor = connection.execute(
        """
        UPDATE notification_deliveries
        SET
            status = 'sent',
            attempt_count = attempt_count + 1,
            last_attempt_at = ?,
            sent_at = ?,
            error_message = NULL,
            response_status_code = ?
        WHERE id = ?
        """,
        (sent_at, sent_at, response_status_code, delivery_id),
    )
    connection.commit()
    logger.info("Marked delivery sent: delivery_id=%s rows=%s", delivery_id, cursor.rowcount)


def mark_delivery_failed(
    connection: sqlite3.Connection,
    delivery_id: int,
    *,
    attempted_at: str,
    error_message: str,
    response_status_code: int | None = None,
) -> None:
    cursor = connection.execute(
        """
        UPDATE notification_deliveries
        SET
            status = 'pending',
            attempt_count = attempt_count + 1,
            last_attempt_at = ?,
            error_message = ?,
            response_status_code = ?
        WHERE id = ?
        """,
        (attempted_at, error_message, response_status_code, delivery_id),
    )
    connection.commit()
    logger.info("Recorded delivery failure: delivery_id=%s rows=%s", delivery_id, cursor.rowcount)


def mark_delivery_failed_final(
    connection: sqlite3.Connection,
    delivery_id: int,
    *,
    attempted_at: str,
    error_message: str,
    response_status_code: int | None = None,
) -> None:
    cursor = connection.execute(
        """
        UPDATE notification_deliveries
        SET
            status = 'failed',
            attempt_count = attempt_count + 1,
            last_attempt_at = ?,
            error_message = ?,
            response_status_code = ?
        WHERE id = ?
        """,
        (attempted_at, error_message, response_status_code, delivery_id),
    )
    connection.commit()
    logger.info("Recorded final delivery failure: delivery_id=%s rows=%s", delivery_id, cursor.rowcount)


def find_pending_notifications(connection: sqlite3.Connection) -> list[dict]:
    # Runtime Discord send loop only handles pending Discord notifications for new posts.
    rows = connection.execute(
        """
        SELECT
            notification_deliveries.id AS delivery_id,
            notification_deliveries.notification_type,
            notification_deliveries.channel_type,
            notification_deliveries.status,
            notification_deliveries.attempt_count,
            notification_deliveries.created_at,
            notification_deliveries.last_attempt_at,
            notification_deliveries.sent_at,
            notification_deliveries.error_message,
            notification_deliveries.response_status_code,
            notification_deliveries.board_type,
            notification_deliveries.thread_id,
            COALESCE(posts.title, notification_deliveries.title) AS title,
            posts.category,
            posts.published_at,
            COALESCE(posts.url, notification_deliveries.url) AS url,
            posts.first_seen_at
        FROM notification_deliveries
        LEFT JOIN posts
            ON posts.board_type = notification_deliveries.board_type
            AND posts.thread_id = notification_deliveries.thread_id
        WHERE notification_deliveries.status = 'pending'
            AND notification_deliveries.notification_type = 'new_post'
            AND notification_deliveries.channel_type = 'discord'
        ORDER BY posts.first_seen_at ASC, notification_deliveries.created_at ASC
        """
    ).fetchall()
    pending = [dict(row) for row in rows]
    logger.debug("Pending notification query complete: count=%s", len(pending))
    return pending
