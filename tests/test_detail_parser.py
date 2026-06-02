import unittest
from pathlib import Path

from app.parsers.detail_parser import parse_notice_detail_body


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class DetailParserTest(unittest.TestCase):
    def test_parse_notice_detail_body_normalizes_meaningful_text(self) -> None:
        html = (FIXTURE_DIR / "notice_detail.html").read_text(encoding="utf-8")

        body = parse_notice_detail_body(html)

        self.assertEqual(
            body,
            "\n".join(
                [
                    "Hello Milletians!",
                    "Maintenance starts at 10:00.",
                    "Please reconnect after the patch.",
                    "Reward claims remain available.",
                ]
            ),
        )

    def test_parse_notice_detail_body_returns_empty_string_when_body_missing(self) -> None:
        body = parse_notice_detail_body("<html><body><h1>Only title</h1></body></html>")

        self.assertEqual(body, "")


if __name__ == "__main__":
    unittest.main()
