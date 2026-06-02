import unittest
from pathlib import Path
from unittest.mock import patch

from app.collectors.notice import fetch_notice_detail_body


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class NoticeCollectorTest(unittest.TestCase):
    def test_fetch_notice_detail_body_fetches_and_parses_url(self) -> None:
        html = (FIXTURE_DIR / "notice_detail.html").read_text(encoding="utf-8")

        with patch("app.collectors.notice.get", return_value=html) as get:
            body = fetch_notice_detail_body("https://example.com/News/Notice/123")

        get.assert_called_once_with("https://example.com/News/Notice/123")
        self.assertIn("Maintenance starts at 10:00.", body)
        self.assertNotIn("Maintenance Notice", body)


if __name__ == "__main__":
    unittest.main()
