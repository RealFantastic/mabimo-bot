import unittest
from unittest.mock import patch

from app.collectors.event import EVENT_URL, fetch_event_list


class EventCollectorTest(unittest.TestCase):
    def test_fetch_event_list_parses_official_board_list(self) -> None:
        html = """
        <div class="list_area" data-mm-boardlist>
            <ul>
                <li class="item" data-mm-listitem data-threadid="789">
                    <div class="order_1">
                        <div class="type">진행중</div>
                        <a class="title"><span>출석 이벤트</span></a>
                    </div>
                    <div class="order_2">
                        <div class="date">
                            <span>2026.7.2(목) 점검 후 ~ 2026.7.16(목) 오전 5시 59분까지</span>
                        </div>
                    </div>
                </li>
                <li class="item" data-mm-listitem data-threadid="skip-no-title">
                    <div class="order_1">
                        <div class="type">지난 이벤트</div>
                    </div>
                </li>
            </ul>
        </div>
        """

        with patch("app.collectors.event.get", return_value=html) as get:
            events = fetch_event_list()

        get.assert_called_once_with(EVENT_URL)
        self.assertEqual(
            events,
            [
                {
                    "thread_id": "789",
                    "category": "진행중",
                    "title": "출석 이벤트",
                    "url": "https://mabinogimobile.nexon.com/News/Events/789",
                    "published_at": "2026.7.2(목) 점검 후 ~ 2026.7.16(목) 오전 5시 59분까지",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
