import logging
import re
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Generator, LiteralString

from selenium import webdriver
from selenium.common.exceptions import MoveTargetOutOfBoundsException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utilities import chapter_link, get_book_name, parse_chapters

logger = logging.getLogger("parser")


class ElementType(StrEnum):
    Text = auto()
    Image = auto()


@dataclass
class Element:
    type: ElementType
    content: str


class Page:
    elements: dict[str, tuple[LiteralString, str]] = {
        # "app": (By.ID, "app"),
        # "something": (By.XPATH, "//div[@class='text']/p"),
    }

    def __init__(self, driver: webdriver.Chrome, timeout: float = 1.) -> None:
        self._driver = driver
        self._elements: dict[str, WebElement] = {}
        for element, mark in self.elements.items():
            self._elements[element] = WebDriverWait(self._driver, timeout).until(
                EC.visibility_of_element_located(mark)
            )


class ChapterPage(Page):
    elements: dict[str, tuple[LiteralString, str]] = {
        "header": (By.XPATH, "//h1"),
        "text_block": (By.XPATH, "//main/div[@class='text-content']"),
        "next_chapter": (By.XPATH, "//div/a[@type='button'][last()]/span"),
    }

    def title(self) -> str:
        title = self._elements["header"].get_attribute("innerHTML")
        return re.sub(r"[ ]?<!--(.*?)-->", "", title).strip()
    
    def content(self) -> Generator[Element, None, None]:
        childs = self._elements["text_block"].find_elements(By.CSS_SELECTOR, "*")
        for elem in childs:
            if elem.tag_name == "p":
                result = Element(ElementType.Text, elem.get_attribute("innerHTML"))
            elif elem.tag_name == "img":
                result = Element(ElementType.Image, elem.get_attribute("src"))
            else:
                # logger.warn("Unknown element type found!")
                continue
            yield result
    
    def next_chapter(self, by_link: bool = False) -> bool:
        next_chapter = self._elements["next_chapter"]
        if "К Тайтлу" == next_chapter.get_attribute("innerHTML"):
            return False
        if by_link:
            self._driver.get(next_chapter.parent.get_attribute("href"))
            return True
        url = self._driver.current_url
        while True:
            actions = (ActionChains(self._driver)
                    .move_to_element(next_chapter)
                    .click(next_chapter))
            try:
                actions.perform()
            except MoveTargetOutOfBoundsException:
                continue
            if self._driver.current_url == url:
                logger.warn("Failed to advance page!")
                continue
            current_handles = self._driver.window_handles
            if current_handles > 1:
                for handle in current_handles[1:]:
                    self._driver.switch_to.window(handle)
                    self._driver.close()
                else:
                    self._driver.switch_to.window(current_handles[0])
            return True


class TitlePage(Page):
    elements: dict[str, tuple[LiteralString, str]] = {
        "title": (By.XPATH, "//h1/span"),
        "start_reading": (By.XPATH, "//div[button | div]/a[@type='button'][span/following-sibling::span]"),  # noqa: E501
        "cover": (By.XPATH, "//div[@class='cover']/div/img"),
    }

    def title(self) -> str:
        return self._elements["title"].get_attribute("innerHTML")

    def cover(self) -> str:
        return self._elements["cover"].get_attribute("src")

    def to_chapter(self, num: int | None = None):
        try:
            book_name = get_book_name(self._driver.current_url)
            if not num or not book_name:
                raise AttributeError()
            chapters = parse_chapters(book_name)
            chapter = chapters[num]
            chapter_url = chapter_link(book_name, chapter)
            self._driver.get(chapter_url)
            logger.debug("Successfully loaded volume %s chapter %s '%s'",
                          chapter.volume, chapter.number, chapter.name)
        except (AttributeError, TypeError):
            logger.info("Starting from the first chapter")
            self._elements["start_reading"].click()
        except IndexError:
            logger.warn("Failed to get %d chapter, there only %d chapters",
                         num, len(chapters))
            logger.info("Starting from the first chapter")
            self._elements["start_reading"].click()
