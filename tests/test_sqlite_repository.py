import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.repositories.sqlite_repository import (
    create_pending_delivery,
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
    mark_delivery_failed,
    mark_delivery_sent,
)


class SqliteRepositoryTest(unittest.TestCase):
    def test_new_posts_schema_does_not_include_notified_at(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)

                columns = [
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(posts)").fetchall()
                ]

            self.assertEqual(
                columns,
                [
                    "thread_id",
                    "board_type",
                    "title",
                    "category",
                    "published_at",
                    "url",
                    "first_seen_at",
                ],
            )

    def test_failed_notification_remains_pending_until_marked_sent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                insert_post(
                    connection,
                    _post(),
                    board_type="notice",
                    first_seen_at="2026-06-02T00:00:00+00:00",
                )

                pending = find_pending_notifications(connection)
                self.assertEqual([delivery["thread_id"] for delivery in pending], ["123"])
                delivery_id = pending[0]["delivery_id"]

                mark_delivery_failed(
                    connection,
                    delivery_id,
                    attempted_at="2026-06-02T00:01:00+00:00",
                    error_message="temporary failure",
                    response_status_code=500,
                )
                retried = find_pending_notifications(connection)
                self.assertEqual([delivery["thread_id"] for delivery in retried], ["123"])
                self.assertEqual(retried[0]["attempt_count"], 1)
                self.assertEqual(retried[0]["error_message"], "temporary failure")

                mark_delivery_sent(
                    connection,
                    delivery_id,
                    sent_at="2026-06-02T00:02:00+00:00",
                    response_status_code=204,
                )

                self.assertEqual(find_pending_notifications(connection), [])

    def test_env_db_path_overrides_default(self) -> None:
        previous = os.environ.get("MABIMO_DB_PATH")

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "custom.db"
            os.environ["MABIMO_DB_PATH"] = str(db_path)
            try:
                with closing(connect()) as connection:
                    initialize(connection)
            finally:
                if previous is None:
                    os.environ.pop("MABIMO_DB_PATH", None)
                else:
                    os.environ["MABIMO_DB_PATH"] = previous

            self.assertTrue(db_path.exists())

    def test_initialize_keeps_existing_notified_at_schema_usable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE posts (
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
                connection.commit()

                initialize(connection)
                insert_post(
                    connection,
                    _post(),
                    board_type="notice",
                    first_seen_at="2026-06-02T00:00:00+00:00",
                )

                pending = find_pending_notifications(connection)

            self.assertEqual(pending[0]["thread_id"], "123")

    def test_initialize_backfills_legacy_notified_at_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE posts (
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
                connection.executemany(
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "sent-1",
                            "notice",
                            "sent title",
                            "notice",
                            "2026-06-02",
                            "https://example.com/sent-1",
                            "2026-06-02T00:00:00+00:00",
                            "2026-06-02T00:01:00+00:00",
                        ),
                        (
                            "pending-1",
                            "notice",
                            "pending title",
                            "notice",
                            "2026-06-02",
                            "https://example.com/pending-1",
                            "2026-06-02T00:00:00+00:00",
                            None,
                        ),
                    ],
                )
                connection.commit()

                initialize(connection)
                initialize(connection)

                rows = [
                    dict(row)
                    for row in connection.execute(
                        """
                        SELECT
                            thread_id,
                            notification_type,
                            channel_type,
                            status,
                            attempt_count,
                            sent_at
                        FROM notification_deliveries
                        ORDER BY thread_id
                        """
                    ).fetchall()
                ]

            self.assertEqual(
                rows,
                [
                    {
                        "thread_id": "pending-1",
                        "notification_type": "new_post",
                        "channel_type": "discord",
                        "status": "pending",
                        "attempt_count": 0,
                        "sent_at": None,
                    },
                    {
                        "thread_id": "sent-1",
                        "notification_type": "new_post",
                        "channel_type": "discord",
                        "status": "sent",
                        "attempt_count": 1,
                        "sent_at": "2026-06-02T00:01:00+00:00",
                    },
                ],
            )

    def test_initialize_creates_notification_deliveries_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)

                table_names = {
                    row["name"]
                    for row in connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                        """
                    ).fetchall()
                }
                columns = {
                    row["name"]: dict(row)
                    for row in connection.execute(
                        "PRAGMA table_info(notification_deliveries)"
                    ).fetchall()
                }
                foreign_keys = connection.execute(
                    "PRAGMA foreign_key_list(notification_deliveries)"
                ).fetchall()

            self.assertIn("notification_deliveries", table_names)
            self.assertEqual(foreign_keys, [])
            self.assertEqual(
                list(columns),
                [
                    "id",
                    "notification_type",
                    "channel_type",
                    "status",
                    "board_type",
                    "thread_id",
                    "title",
                    "url",
                    "message",
                    "attempt_count",
                    "created_at",
                    "last_attempt_at",
                    "sent_at",
                    "error_message",
                    "response_status_code",
                ],
            )
            self.assertEqual(columns["id"]["type"], "INTEGER")
            self.assertEqual(columns["id"]["pk"], 1)
            self.assertEqual(columns["notification_type"]["notnull"], 1)
            self.assertIsNone(columns["notification_type"]["dflt_value"])
            self.assertEqual(columns["channel_type"]["notnull"], 1)
            self.assertIsNone(columns["channel_type"]["dflt_value"])
            self.assertEqual(columns["status"]["notnull"], 1)
            self.assertEqual(columns["status"]["dflt_value"], "'pending'")
            self.assertEqual(columns["board_type"]["notnull"], 0)
            self.assertEqual(columns["thread_id"]["notnull"], 0)
            self.assertEqual(columns["title"]["notnull"], 0)
            self.assertEqual(columns["url"]["notnull"], 0)
            self.assertEqual(columns["message"]["notnull"], 1)
            self.assertEqual(columns["message"]["dflt_value"], "''")
            self.assertEqual(columns["attempt_count"]["notnull"], 1)
            self.assertEqual(columns["attempt_count"]["dflt_value"], "0")
            self.assertEqual(columns["created_at"]["notnull"], 1)
            self.assertEqual(columns["created_at"]["dflt_value"], "CURRENT_TIMESTAMP")
            self.assertEqual(columns["last_attempt_at"]["notnull"], 0)
            self.assertEqual(columns["sent_at"]["notnull"], 0)
            self.assertEqual(columns["error_message"]["notnull"], 0)
            self.assertEqual(columns["response_status_code"]["notnull"], 0)

    def test_create_pending_delivery_is_idempotent_for_real_post_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                insert_post(
                    connection,
                    _post(),
                    board_type="notice",
                    first_seen_at="2026-06-02T00:00:00+00:00",
                )
                create_pending_delivery(connection, _post(), board_type="notice")

                rows = connection.execute(
                    """
                    SELECT thread_id, status
                    FROM notification_deliveries
                    WHERE notification_type = 'new_post'
                        AND channel_type = 'discord'
                        AND thread_id = '123'
                    """
                ).fetchall()

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "pending")

    def test_find_pending_notifications_returns_only_pending_discord_new_posts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                connection.executemany(
                    """
                    INSERT INTO notification_deliveries (
                        notification_type,
                        channel_type,
                        status,
                        board_type,
                        thread_id,
                        title,
                        url
                    )
                    VALUES (?, ?, 'pending', ?, ?, ?, ?)
                    """,
                    [
                        (
                            "test",
                            "discord",
                            None,
                            None,
                            "test delivery",
                            "https://example.com/test",
                        ),
                        (
                            "new_post",
                            "slack",
                            "notice",
                            "slack-1",
                            "slack title",
                            "https://example.com/slack-1",
                        ),
                        (
                            "new_post",
                            "discord",
                            "notice",
                            "discord-1",
                            "discord title",
                            "https://example.com/discord-1",
                        ),
                    ],
                )
                connection.commit()

                pending = find_pending_notifications(connection)

            self.assertEqual([delivery["thread_id"] for delivery in pending], ["discord-1"])
            self.assertEqual(pending[0]["notification_type"], "new_post")
            self.assertEqual(pending[0]["channel_type"], "discord")

    def test_notification_deliveries_rejects_negative_attempt_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO notification_deliveries (
                            notification_type,
                            channel_type,
                            message,
                            attempt_count
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        ("test", "discord", "test message", -1),
                    )

    def test_notification_deliveries_rejects_invalid_type_channel_and_status(self) -> None:
        invalid_rows = [
            ("unsupported_notification_type", "discord", "pending"),
            ("test", "unsupported_channel_type", "pending"),
            ("test", "discord", "unsupported_status"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)

                for notification_type, channel_type, status in invalid_rows:
                    with self.subTest(
                        notification_type=notification_type,
                        channel_type=channel_type,
                        status=status,
                    ):
                        with self.assertRaises(sqlite3.IntegrityError):
                            connection.execute(
                                """
                                INSERT INTO notification_deliveries (
                                    notification_type,
                                    channel_type,
                                    status,
                                    message
                                )
                                VALUES (?, ?, ?, ?)
                                """,
                                (
                                    notification_type,
                                    channel_type,
                                    status,
                                    "test message",
                                ),
                            )


def _post() -> dict:
    return {
        "thread_id": "123",
        "title": "notice title",
        "category": "notice",
        "published_at": "2026-06-02",
        "url": "https://example.com/notice/123",
    }


if __name__ == "__main__":
    unittest.main()
