from bs4 import BeautifulSoup

from app.utils.http import get
from app.utils.logger import get_logger


BASE_URL = "https://mabinogimobile.nexon.com"
# 공지사항 URL 작성
NOTICE_URL = "https://mabinogimobile.nexon.com/News/notice"
logger = get_logger(__name__)


def fetch_notice_list() -> list[dict]:
    logger.debug("Fetching notice list: url=%s", NOTICE_URL)
    html = get(NOTICE_URL)
    logger.debug("Notice list fetched: chars=%s", len(html))
    soup = BeautifulSoup(html, "lxml")

    notices: list[dict] = []
    list_area = soup.select_one('div.list_area[data-mm-boardlist]')
    if not list_area:
        logger.warning("Notice list area not found")
        return notices

    items = list_area.select('li.item[data-mm-listitem][data-threadid]')
    logger.debug("Notice list items found: count=%s", len(items))

    for item in items:
        thread_id = item.get("data-threadid", "").strip()
        if not thread_id:
            logger.debug("Skipping notice item without thread_id")
            continue

        type_tag = item.select_one("div.order_1 div.type > span")
        title_tag = item.select_one("div.order_1 a.title > span")
        published_at_tag = item.select_one("div.order_2 div.sub_info div.date > span")

        category = type_tag.get_text(strip=True) if type_tag else ""
        title = title_tag.get_text(strip=True) if title_tag else ""
        published_at = published_at_tag.get_text(strip=True) if published_at_tag else ""

        if not title:
            logger.debug("Skipping notice item without title: thread_id=%s", thread_id)
            continue
        url = f"{BASE_URL}/News/Notice/{thread_id}"
        notices.append(
            {
                "thread_id": thread_id,
                "category": category,
                "title": title,
                "url": url,
                "published_at": published_at,
            }
        )

    logger.info("Notice list parsed: count=%s", len(notices))
    return notices
