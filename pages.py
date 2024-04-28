from selenium import webdriver
from selenium.common.exceptions import MoveTargetOutOfBoundsException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains

from typing import LiteralString, Generator
from enum import StrEnum, auto
from dataclasses import dataclass


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
        "header": (By.XPATH, "//div[@class='jp_m']/h1"),
        "text_block": (By.XPATH, "//main[@class='jp_bm']/div[@class='text-content']"),
        "next_chapter": (By.XPATH, "//div[@class='qq_ar']/a[last()]/span"),
    }

    def title(self) -> str:
        return self._elements["header"].get_attribute("innerHTML")
    
    def content(self) -> Generator[Element, None, None]:
        childs = self._elements["text_block"].find_elements(By.CSS_SELECTOR, "*")
        for elem in childs:
            if elem.tag_name == "p":
                result = Element(ElementType.Text, elem.get_attribute("innerHTML"))
            elif elem.tag_name == "img":
                result = Element(ElementType.Image, elem.get_attribute("src"))
            else:
                # print("Unknown element type found!")
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
                print("[Warning]: failed to advance page!")
                continue
            return True


class TitlePage(Page):
    elements: dict[str, tuple[LiteralString, str]] = {
        "title": (By.XPATH, "//h1[@class='no_nq']/span"),
        "start_reading": (By.XPATH, "//div[@class='gq_bq']/a[contains(@class, 'btn')]"),
        "cover": (By.XPATH, "//div[@class='cover']/div/img"),
    }

    def title(self) -> str:
        return self._elements["title"].get_attribute("innerHTML")

    def cover(self) -> str:
        return self._elements["cover"].get_attribute("src")

    def to_chapter(self, num: int):
        self._elements["start_reading"].click()
