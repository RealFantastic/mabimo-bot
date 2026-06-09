import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from app.main import BoardSource, parse_args, run_once, send_pending_notifications
from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
)
from app.services.notifier_service import DiscordNotificationError


class MainTest(unittest.TestCase):
    def test_run_once_calls_existing_detection_flow_for_manual_execution(self) -> None:
        connection = Mock()
        collector = Mock(return_value=[_post()])
        board_sources = (BoardSource(board_type="notice", fetch=collector),)

        with patch("app.main.connect", return_value=connection):
            with patch("app.main.closing", _closing_passthrough):
                with patch("app.main.initialize") as initialize:
                    with patch("app.main.detect_and_store_new_posts", return_value=[_post()]) as detect:
                        with patch("app.main.send_pending_notifications", return_value=(1, 0)) as send:
                            summary = run_once(
                                webhook_url="https://discord.example/hook",
                                board_sources=board_sources,
                            )

        initialize.assert_called_once_with(connection)
        collector.assert_called_once_with()
        detect.assert_called_once_with(connection, [_post()], board_type="notice")
        send.assert_called_once_with(connection, "https://discord.example/hook")
        self.assertEqual(summary, {"fetched": 1, "new": 1, "sent": 1, "failed": 0})

    def test_run_once_iterates_multiple_board_sources(self) -> None:
        connection = Mock()
        notice = _post(thread_id="notice-1")
        update = _post(thread_id="update-1")
        board_sources = (
            BoardSource(board_type="notice", fetch=Mock(return_value=[notice])),
            BoardSource(board_type="update", fetch=Mock(return_value=[update])),
        )

        with patch("app.main.connect", return_value=connection):
            with patch("app.main.closing", _closing_passthrough):
                with patch("app.main.initialize"):
                    with patch(
                        "app.main.detect_and_store_new_posts",
                        side_effect=lambda _connection, posts, *, board_type: posts,
                    ) as detect:
                        with patch("app.main.send_pending_notifications", return_value=(2, 0)):
                            summary = run_once(
                                webhook_url="https://discord.example/hook",
                                board_sources=board_sources,
                            )

        self.assertEqual(
            [call.kwargs["board_type"] for call in detect.call_args_list],
            ["notice", "update"],
        )
        self.assertEqual(summary["fetched"], 2)
        self.assertEqual(summary["new"], 2)

    def test_run_once_isolates_board_failure_and_still_sends_pending_notifications(self) -> None:
        connection = Mock()
        good_post = _post(thread_id="notice-1")
        board_sources = (
            BoardSource(board_type="notice", fetch=Mock(return_value=[good_post])),
            BoardSource(board_type="update", fetch=Mock(side_effect=RuntimeError("boom"))),
        )

        with patch("app.main.connect", return_value=connection):
            with patch("app.main.closing", _closing_passthrough):
                with patch("app.main.initialize"):
                    with patch("app.main.detect_and_store_new_posts", return_value=[good_post]) as detect:
                        with patch("app.main.send_pending_notifications", return_value=(1, 0)) as send:
                            summary = run_once(
                                webhook_url="https://discord.example/hook",
                                board_sources=board_sources,
                            )

        detect.assert_called_once_with(connection, [good_post], board_type="notice")
        send.assert_called_once_with(connection, "https://discord.example/hook")
        self.assertEqual(
            summary,
            {"fetched": 1, "new": 1, "sent": 1, "failed": 1},
        )

    def test_parse_args_defaults_to_run_once_and_scheduler_is_explicit(self) -> None:
        self.assertEqual(parse_args([]).command, "run-once")
        self.assertEqual(parse_args(["run-once"]).command, "run-once")
        self.assertEqual(parse_args(["scheduler"]).command, "scheduler")

    def test_parse_args_rejects_invalid_interval_without_traceback(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            parse_args(["scheduler", "--interval-minutes", "0"])

        self.assertEqual(raised.exception.code, 2)

    def test_send_pending_notifications_retries_pending_post(self) -> None:
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
                send = Mock(
                    side_effect=[
                        DiscordNotificationError("first send failed"),
                        None,
                    ]
                )

                with patch("app.main.send_discord_notification", send):
                    self.assertEqual(
                        send_pending_notifications(connection, "https://discord.example/hook"),
                        (0, 1),
                    )
                    self.assertEqual(
                        send_pending_notifications(connection, "https://discord.example/hook"),
                        (1, 0),
                    )

                self.assertEqual(find_pending_notifications(connection), [])

        self.assertEqual(send.call_count, 2)
        retried_post = send.call_args.args[1]
        self.assertEqual(retried_post["thread_id"], "123")


def _post(thread_id: str = "123") -> dict:
    return {
        "thread_id": thread_id,
        "title": "notice title",
        "category": "notice",
        "published_at": "2026-06-02",
        "url": f"https://example.com/notice/{thread_id}",
    }


class _closing_passthrough:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc, traceback):
        return False


if __name__ == "__main__":
    unittest.main()
