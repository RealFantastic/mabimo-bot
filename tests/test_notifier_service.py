import unittest
from unittest.mock import Mock, patch

import httpx

from app.services.notifier_service import (
    DiscordNotificationError,
    send_discord_notification,
)


class NotifierServiceTest(unittest.TestCase):
    def test_webhook_payload_disables_mentions(self) -> None:
        request = httpx.Request("POST", "https://discord.example/webhook/token")
        response = httpx.Response(204, request=request)

        with patch("app.services.notifier_service.httpx.post", return_value=response) as post:
            send_discord_notification("https://discord.example/webhook/token", _post())

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["allowed_mentions"], {"parse": []})

    def test_http_error_message_does_not_include_webhook_url(self) -> None:
        webhook_url = "https://discord.example/webhook/secret-token"
        request = httpx.Request("POST", webhook_url)
        response = httpx.Response(401, request=request)

        with patch("app.services.notifier_service.httpx.post", return_value=response):
            with self.assertRaises(DiscordNotificationError) as raised:
                send_discord_notification(webhook_url, _post())

        self.assertIn("HTTP 401", str(raised.exception))
        self.assertNotIn(webhook_url, str(raised.exception))
        self.assertNotIn("secret-token", str(raised.exception))

    def test_rate_limit_retries_once(self) -> None:
        request = httpx.Request("POST", "https://discord.example/webhook/token")
        rate_limited = httpx.Response(
            429,
            request=request,
            json={"retry_after": 0},
        )
        success = httpx.Response(204, request=request)
        post = Mock(side_effect=[rate_limited, success])

        with patch("app.services.notifier_service.httpx.post", post):
            with patch("app.services.notifier_service.time.sleep") as sleep:
                send_discord_notification(str(request.url), _post())

        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(0.0)


def _post() -> dict:
    return {
        "thread_id": "123",
        "title": "@everyone notice",
        "category": "notice",
        "published_at": "2026-06-02",
        "url": "https://example.com/notice/123",
    }


if __name__ == "__main__":
    unittest.main()
