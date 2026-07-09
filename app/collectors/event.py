from bs4 import BeautifulSoup

from app.utils.http import get
from app.utils.logger import get_logger


BASE_URL = "https://mabinogimobile.nexon.com"
EVENT_URL = "https://mabinogimobile.nexon.com/News/Events"
logger = get_logger(__name__)


def fetch_event_list() -> list[dict]:
    logger.debug("Fetching event list: url=%s", EVENT_URL)
    html = get(EVENT_URL)
    logger.debug("Event list fetched: chars=%s", len(html))
    soup = BeautifulSoup(html, "lxml")

    events: list[dict] = []
    list_area = soup.select_one('div.list_area[data-mm-boardlist]')
    if not list_area:
        logger.warning("Event list area not found")
        return events

    items = list_area.select('li.item[data-mm-listitem][data-threadid]')
    logger.debug("Event list items found: count=%s", len(items))

    for item in items:
        thread_id = item.get("data-threadid", "").strip()
        if not thread_id:
            logger.debug("Skipping event item without thread_id")
            continue

        type_tag = item.select_one("div.order_1 div.type")
        title_tag = item.select_one("div.order_1 a.title > span")
        period_tag = item.select_one("div.order_2 div.date > span")

        category = type_tag.get_text(strip=True) if type_tag else ""
        title = title_tag.get_text(strip=True) if title_tag else ""
        period = period_tag.get_text(strip=True) if period_tag else ""

        if not title:
            logger.debug("Skipping event item without title: thread_id=%s", thread_id)
            continue

        url = f"{BASE_URL}/News/Events/{thread_id}"
        events.append(
            {
                "thread_id": thread_id,
                "category": category,
                "title": title,
                "url": url,
                "published_at": period,
            }
        )

    logger.info("Event list parsed: count=%s", len(events))
    return events
