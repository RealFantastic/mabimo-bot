import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
)
from app.services.diff_service import detect_and_store_new_posts
from app.services.summary_service import fallback_summary


class DiffServiceTest(unittest.TestCase):
    def test_detect_and_store_new_posts_collects_detail_body_for_new_posts_only(self) -> None:
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
                detail_body_fetcher = Mock(return_value="Collected body text")

                new_posts = detect_and_store_new_posts(
                    connection,
                    [
                        _post(thread_id="existing", url="https://example.com/existing"),
                        _post(thread_id="new", url="https://example.com/new"),
                    ],
                    board_type="notice",
                    detail_body_fetcher=detail_body_fetcher,
                )

                self.assertEqual([post["thread_id"] for post in new_posts], ["new"])
                detail_body_fetcher.assert_called_once_with("https://example.com/new")

                pending_by_id = {
                    post["thread_id"]: post for post in find_pending_notifications(connection)
                }
                self.assertEqual(pending_by_id["new"]["detail_body"], "Collected body text")
                self.assertEqual(pending_by_id["existing"]["detail_body"], "")

    def test_detect_and_store_new_posts_summarizes_and_stores_new_posts_only(self) -> None:
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
                detail_body_fetcher = Mock(return_value="Collected body text")
                summary_generator = Mock(return_value="🧾 요약\n- 저장된 요약")

                new_posts = detect_and_store_new_posts(
                    connection,
                    [
                        _post(thread_id="existing", url="https://example.com/existing"),
                        _post(thread_id="new", url="https://example.com/new"),
                    ],
                    board_type="notice",
                    detail_body_fetcher=detail_body_fetcher,
                    summary_generator=summary_generator,
                )

                self.assertEqual([post["thread_id"] for post in new_posts], ["new"])
                summary_generator.assert_called_once()
                summarized_post = summary_generator.call_args.args[0]
                self.assertEqual(summarized_post["thread_id"], "new")
                self.assertEqual(summarized_post["detail_body"], "Collected body text")

                pending_by_id = {
                    post["thread_id"]: post for post in find_pending_notifications(connection)
                }
                self.assertEqual(pending_by_id["new"]["summary_text"], "🧾 요약\n- 저장된 요약")
                self.assertEqual(pending_by_id["existing"]["summary_text"], "")

    def test_detect_and_store_new_posts_stores_fallback_summary_when_generator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                detail_body_fetcher = Mock(return_value="본문 수집은 성공했습니다.")
                summary_generator = Mock(side_effect=RuntimeError("summary failed"))

                with unittest.mock.patch("builtins.print"):
                    detect_and_store_new_posts(
                        connection,
                        [_post(thread_id="new", url="https://example.com/new")],
                        board_type="notice",
                        detail_body_fetcher=detail_body_fetcher,
                        summary_generator=summary_generator,
                    )

                pending = find_pending_notifications(connection)

            self.assertEqual(
                pending[0]["summary_text"],
                "🧾 요약\n- 본문 수집은 성공했습니다.",
            )

    def test_detect_and_store_new_posts_skips_summary_generation_for_empty_detail_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                detail_body_fetcher = Mock(return_value="")
                summary_generator = Mock(return_value="should not be stored")

                detect_and_store_new_posts(
                    connection,
                    [_post(thread_id="new", url="https://example.com/new")],
                    board_type="notice",
                    detail_body_fetcher=detail_body_fetcher,
                    summary_generator=summary_generator,
                )

                pending = find_pending_notifications(connection)

            summary_generator.assert_not_called()
            self.assertEqual(pending[0]["summary_text"], fallback_summary(""))

    def test_detect_and_store_new_posts_skips_summary_generation_for_whitespace_detail_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with closing(connect(db_path)) as connection:
                initialize(connection)
                detail_body_fetcher = Mock(return_value=" \n\t ")
                summary_generator = Mock(return_value="should not be stored")

                detect_and_store_new_posts(
                    connection,
                    [_post(thread_id="new", url="https://example.com/new")],
                    board_type="notice",
                    detail_body_fetcher=detail_body_fetcher,
                    summary_generator=summary_generator,
                )

                pending = find_pending_notifications(connection)

            summary_generator.assert_not_called()
            self.assertEqual(pending[0]["summary_text"], fallback_summary(""))


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
