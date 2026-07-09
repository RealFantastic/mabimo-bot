import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from app.main import (
    BOARD_SOURCES,
    BoardSource,
    parse_args,
    run_once,
    send_pending_notifications,
    send_test_notification,
)
from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
)
from app.services.notifier_service import DiscordNotificationError


class MainTest(unittest.TestCase):
    def test_default_run_once_sources_include_notice_and_event_boards(self) -> None:
        self.assertEqual(
            [source.board_type for source in BOARD_SOURCES],
            ["notice", "event"],
        )

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
        self.assertEqual(parse_args(["send-test"]).command, "send-test")

    def test_parse_args_accepts_send_test_message(self) -> None:
        args = parse_args(["send-test", "--message", "hello"])

        self.assertEqual(args.command, "send-test")
        self.assertEqual(args.message, "hello")

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
                columns = [
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(posts)").fetchall()
                ]
                self.assertNotIn("notified_at", columns)
                delivery = connection.execute(
                    """
                    SELECT
                        status,
                        attempt_count,
                        sent_at,
                        last_attempt_at,
                        error_message,
                        response_status_code
                    FROM notification_deliveries
                    WHERE thread_id = ?
                    """,
                    ("123",),
                ).fetchone()

        self.assertEqual(send.call_count, 2)
        retried_post = send.call_args.args[1]
        self.assertEqual(retried_post["thread_id"], "123")
        self.assertEqual(delivery["status"], "sent")
        self.assertEqual(delivery["attempt_count"], 2)
        self.assertIsNotNone(delivery["sent_at"])
        self.assertIsNotNone(delivery["last_attempt_at"])
        self.assertIsNone(delivery["error_message"])
        self.assertEqual(delivery["response_status_code"], 204)

    def test_send_pending_notifications_without_webhook_records_retryable_failure(self) -> None:
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

                self.assertEqual(send_pending_notifications(connection, None), (0, 1))

                pending = find_pending_notifications(connection)

            self.assertEqual([delivery["thread_id"] for delivery in pending], ["123"])
            self.assertEqual(pending[0]["status"], "pending")
            self.assertEqual(pending[0]["attempt_count"], 1)
            self.assertEqual(pending[0]["error_message"], "DISCORD_WEBHOOK_URL is not configured.")

    def test_send_test_notification_records_test_delivery_without_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with patch.dict("os.environ", {"MABIMO_DB_PATH": str(db_path)}):
                with patch("app.main.send_discord_message", return_value=204) as send:
                    summary = send_test_notification(
                        webhook_url="https://discord.example/hook",
                        message="test message",
                    )

                with closing(connect(db_path)) as connection:
                    posts = connection.execute("SELECT * FROM posts").fetchall()
                    delivery = connection.execute(
                        """
                        SELECT
                            notification_type,
                            channel_type,
                            status,
                            board_type,
                            thread_id,
                            message,
                            attempt_count,
                            sent_at,
                            response_status_code
                        FROM notification_deliveries
                        """
                    ).fetchone()

        self.assertEqual(summary, {"sent": 1, "failed": 0})
        send.assert_called_once_with(
            "https://discord.example/hook",
            "test message",
            log_context="test_delivery_id=1",
        )
        self.assertEqual(posts, [])
        self.assertEqual(delivery["notification_type"], "test")
        self.assertEqual(delivery["channel_type"], "discord")
        self.assertEqual(delivery["status"], "sent")
        self.assertIsNone(delivery["board_type"])
        self.assertIsNone(delivery["thread_id"])
        self.assertEqual(delivery["message"], "test message")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertIsNotNone(delivery["sent_at"])
        self.assertEqual(delivery["response_status_code"], 204)

    def test_send_test_notification_without_webhook_records_final_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with patch.dict("os.environ", {"MABIMO_DB_PATH": str(db_path)}):
                summary = send_test_notification(webhook_url=None, message="test message")

                with closing(connect(db_path)) as connection:
                    delivery = connection.execute(
                        """
                        SELECT status, attempt_count, error_message
                        FROM notification_deliveries
                        """
                    ).fetchone()

        self.assertEqual(summary, {"sent": 0, "failed": 1})
        self.assertEqual(delivery["status"], "failed")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(delivery["error_message"], "DISCORD_WEBHOOK_URL is not configured.")

    def test_send_test_notification_discord_error_records_final_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mabimo.db"

            with patch.dict("os.environ", {"MABIMO_DB_PATH": str(db_path)}):
                with patch(
                    "app.main.send_discord_message",
                    side_effect=DiscordNotificationError("Discord webhook returned HTTP 500", status_code=500),
                ) as send:
                    summary = send_test_notification(
                        webhook_url="https://discord.example/hook",
                        message="test message",
                    )

                with closing(connect(db_path)) as connection:
                    delivery = connection.execute(
                        """
                        SELECT status, attempt_count, error_message, response_status_code
                        FROM notification_deliveries
                        """
                    ).fetchone()

        self.assertEqual(summary, {"sent": 0, "failed": 1})
        send.assert_called_once_with(
            "https://discord.example/hook",
            "test message",
            log_context="test_delivery_id=1",
        )
        self.assertEqual(delivery["status"], "failed")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(delivery["error_message"], "Discord webhook returned HTTP 500")
        self.assertEqual(delivery["response_status_code"], 500)


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
