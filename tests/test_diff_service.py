import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
)
from app.services.diff_service import detect_and_store_new_posts


class DiffServiceTest(unittest.TestCase):
    def test_detect_and_store_new_posts_stores_new_posts_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                insert_post(
                    connection,
                    _post(thread_id="existing", url="https://example.com/existing"),
                    board_type="notice",
                    first_seen_at="2026-06-02T00:00:00+00:00",
                )

                new_posts = detect_and_store_new_posts(
                    connection,
                    [
                        _post(thread_id="existing", url="https://example.com/existing"),
                        _post(thread_id="new", url="https://example.com/new"),
                    ],
                    board_type="notice",
                )

                self.assertEqual([post["thread_id"] for post in new_posts], ["new"])

                pending_by_id = {
                    post["thread_id"]: post for post in find_pending_notifications(connection)
                }
                self.assertEqual(pending_by_id["new"]["url"], "https://example.com/new")
                self.assertEqual(pending_by_id["existing"]["url"], "https://example.com/existing")


def _post(*, thread_id: str, url: str) -> dict:
    return {
        "thread_id": thread_id,
        "title": f"title {thread_id}",
        "category": "notice",
        "published_at": "2026-06-02",
        "url": url,
    }


if __name__ == "__main__":
    unittest.main()
