import os
import sqlite3
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "mabimo.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    resolved_db_path = Path(os.getenv("MABIMO_DB_PATH") or db_path or DEFAULT_DB_PATH)
    connection = sqlite3.connect(resolved_db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            thread_id TEXT PRIMARY KEY,
            board_type TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            published_at TEXT,
            url TEXT NOT NULL,
            detail_body TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            notified_at TEXT
        )
        """
    )
    _ensure_column(
        connection,
        table_name="posts",
        column_name="detail_body",
        definition="TEXT NOT NULL DEFAULT ''",
    )
    connection.commit()


def _ensure_column(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


def find_existing_thread_ids(
    connection: sqlite3.Connection, thread_ids: Iterable[str]
) -> set[str]:
    ids = list(thread_ids)
    if not ids:
        return set()

    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"SELECT thread_id FROM posts WHERE thread_id IN ({placeholders})",
        ids,
    ).fetchall()
    return {row["thread_id"] for row in rows}


def insert_post(
    connection: sqlite3.Connection,
    post: dict,
    *,
    board_type: str,
    first_seen_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO posts (
            thread_id,
            board_type,
            title,
            category,
            published_at,
            url,
            detail_body,
            first_seen_at,
            notified_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            post["thread_id"],
            board_type,
            post["title"],
            post.get("category", ""),
            post.get("published_at", ""),
            post["url"],
            post.get("detail_body", ""),
            first_seen_at,
        ),
    )
    connection.commit()


def update_notified_at(
    connection: sqlite3.Connection, thread_id: str, notified_at: str
) -> None:
    connection.execute(
        "UPDATE posts SET notified_at = ? WHERE thread_id = ?",
        (notified_at, thread_id),
    )
    connection.commit()


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
            detail_body,
            first_seen_at,
            notified_at
        FROM posts
        WHERE notified_at IS NULL
        ORDER BY first_seen_at ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]
