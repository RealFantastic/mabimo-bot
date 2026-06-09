import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from app.main import send_pending_notifications
from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    insert_post,
)
from app.services.notifier_service import DiscordNotificationError


class MainTest(unittest.TestCase):
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
