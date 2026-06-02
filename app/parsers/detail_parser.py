import re

from bs4 import BeautifulSoup


_BODY_SELECTORS = (
    '[data-mm-boardview] .view_body',
    '[data-mm-boardview] .view_cont',
    '[data-mm-boardview] .view_content',
    '[data-mm-boardview] .content',
    '.view_area .view_body',
    '.view_area .view_cont',
    '.view_area .view_content',
    '.board_view .view_body',
    '.board_view .view_cont',
    '.board_view .view_content',
)


def parse_notice_detail_body(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    body = _find_body_element(soup)
    if body is None:
        return ""

    for ignored in body.select("script, style, noscript"):
        ignored.decompose()

    return _normalize_plain_text(body.get_text(separator="\n"))


def _find_body_element(soup: BeautifulSoup):
    for selector in _BODY_SELECTORS:
        element = soup.select_one(selector)
        if element is not None:
            return element
    return None


def _normalize_plain_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    lines = []
    for line in text.splitlines():
        normalized = re.sub(r"[ \t\r\f\v]+", " ", line).strip()
        if normalized:
            lines.append(normalized)
    return "\n".join(lines)
