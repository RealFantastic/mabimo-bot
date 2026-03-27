#imports
from bs4 import BeautifulSoup
from app.utils.http import get


# app/collectors/notice.py

# 공지사항 URL 작성
NOTICE_URL = "https://mabinogimobile.nexon.com/News/notice"

def fetch_notice_list():
    html = get(NOTICE_URL)
    soup = BeautifulSoup(html, "lxml")

    notices = []
    items = soup.select("a") # 임시용 a 태그만 추출

    for item in items[:10]:
        title = item.get_text(strip=True)
        url = item.get("href")

        if not title or not url:
            continue
        if not url.startswith("http"):
            url = "https://mabinogimobile.nexon.com" + url

        notices.append({"title": title, "url": url})

    return notices