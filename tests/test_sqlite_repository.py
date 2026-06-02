import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
    update_notified_at,
)


class SqliteRepositoryTest(unittest.TestCase):
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
                self.assertEqual([post["thread_id"] for post in pending], ["123"])

                update_notified_at(
                    connection,
                    "123",
                    "2026-06-02T00:01:00+00:00",
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
