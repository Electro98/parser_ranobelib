import requests
import re
from dataclasses import dataclass


@dataclass
class Chapter:
    name: str
    volume: str
    number: str


def parse_chapters(book_name: str) -> list[Chapter] | None:
    url = f"https://api.lib.social/api/manga/{book_name}/chapters"
    request = requests.get(url)
    if not request.ok:
        return None
    data = request.json().get("data", {})
    return [
        Chapter(chapter["name"], chapter["volume"], chapter["number"])
        for chapter in data
    ]


def chapter_link(book_name: str, chapter: Chapter) -> str:
    return f"https://ranobelib.me/ru/{book_name}/read/v{chapter.volume}/c{chapter.number}"


def get_book_name(book_url: str) -> str | None:
    # this part can be unnecessary (\?.+)?$
    match = re.search(r"book\/(\d+--[\w-]+)(\?.+)?$", book_url)
    return None if match is None else match.group(1)


def get_book_id(book_url: str) -> str | None:
    match = re.search(r"book\/(\d+)--", book_url)
    return None if match is None else match.group(1)


def sanitize_filepath(filename: str) -> str:
    return re.sub(r"[^\w_. -()]", "", filename)
