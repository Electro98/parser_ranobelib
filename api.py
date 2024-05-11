from dataclasses import InitVar, dataclass, field
from logging import getLogger

import requests
from bs4 import BeautifulSoup

from utilities import Element
from utilities import ElementType as ElemType
from utilities import Url, from_dict, get_book_id, get_book_name

logger = getLogger("parser.api")


@dataclass
class Manga:
    cover: InitVar[dict]
    eng_name: str
    id: int
    name: str
    rus_name: str
    cover_img: str = field(init=False)
    
    def __post_init__(self, cover: dict[str, str]):
        self.cover_img = cover["default"]


@dataclass
class Branch:
    branch_id: int | None


@dataclass
class ChapterInfo:
    branches: list[Branch]
    name: str
    volume: str
    number: str

    def __post_init__(self):
        self.branches = [from_dict(Branch, branch) for branch in self.branches]


@dataclass
class Chapter:
    name: str
    content: list[Element]
    likes_count: int
    number: str
    volume: str

    def __post_init__(self):
        self.content = _parse_content(self.content)


def _parse_content(content: dict | str) -> list[Element]:
    if isinstance(content, str):
        return _parse_html_contern(content)
    elif isinstance(content, dict):
        return _parse_json_contert(content, [])
    else:
        raise TypeError("Unknown type of content detected~!")


def _parse_html_contern(content: str) -> list[Element]:
    soap = BeautifulSoup(content, "html.parser")
    elements = []
    for elem in soap.contents:
        if elem.name == "p":
            elements.append(Element(ElemType.Text, str(elem.string)))
        elif elem.name == "img":
            elements.append(Element(ElemType.ImageLink, elem["src"]))
        else:
            logger.warn("Found unknown element: '%s'", elem)
    return elements


def _parse_json_contert(content: dict, elements: list[Element]):
    match content:
        case {"type": "doc" | "paragraph", "content": list(content_list)}:
            for elem in content_list:
                _parse_json_contert(elem, elements)
        case {"type": "text", "text": str(text)}:
            elements.append(Element(ElemType.Text, text))
        case {"type": "image", "attrs": dict(attrs)}:
            # Just assuming
            for image in attrs.get("images", []):
                img_id = image["image"]
                elements.append(Element(ElemType.ImageId, img_id))
        case {"type": "hardBreak"}:
            pass
        case _:
            logger.warn("Failed to parse content: '%s'", content)
    return elements


class BookAPI:
    def __init__(self, url: str) -> None:
        self._url = url
        self._id = get_book_id(url)
        self._uid = get_book_name(url)
        self._api_link = Url(f"https://api.lib.social/api/manga/{self._uid}")

    def manga_link(self) -> Url:
        return self._api_link

    def chapters_link(self) -> Url:
        return self._api_link / "chapters"

    def chapter_link(self, chapter: ChapterInfo) -> str:
        url = self._api_link / "chapter"
        return url.args(
            number=chapter.number,
            volume=chapter.volume,
        )


def _get_data(link: str | Url) -> dict | None:
    if isinstance(link, Url):
        link = str(link)
    request = requests.get(link)
    if not request.ok:
        return None
    return request.json().get("data", {})


def parse_chapters(link: str | Url) -> list[ChapterInfo] | None:
    data = _get_data(link)
    if not data:
        return None
    return [from_dict(ChapterInfo, chapter) for chapter in data]


def parse_manga_info(link: str | Url) -> Manga | None:
    data = _get_data(link)
    if not data:
        return None
    return from_dict(Manga, data)


def parse_chapter(link: str | Url) -> Chapter | None:
    data = _get_data(link)
    if not data:
        return None
    return from_dict(Chapter, data)
