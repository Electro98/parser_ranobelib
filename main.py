import re
from pathlib import Path

import requests
from ebooklib import epub
from selenium import webdriver
from webdriver_auto_update.chrome_app_utils import ChromeAppUtils
from webdriver_auto_update.webdriver_manager import WebDriverManager

from pages import ChapterPage, ElementType, TitlePage

SELENIUM_FOLDER = "C:\Programs\Selenium"
CACHE_FOLDER = Path("cache/")


def update_selenium(path: str):
    # Using ChromeAppUtils to inspect Chrome application version
    chrome_app_utils = ChromeAppUtils()
    chrome_app_version = chrome_app_utils.get_chrome_version()
    print(f"Chrome application version: {chrome_app_version}")

    # Create an instance of WebDriverManager
    driver_manager = WebDriverManager(path)

    # Call the main method to manage chromedriver
    driver_manager.main()


def parse_id(book_url: str) -> str | None:
    return None


def sanitize_filepath(filename: str) -> str:
    return re.sub(r"[^\w_. -()]", "", filename)


def retrieve_image(url: str):
    response = requests.get(url)
    if response.ok:
        return response.content
    return None


class BookCreator:
    def __init__(self, start_url: str, chapter: int = 0) -> None:
        self._driver = webdriver.Chrome()
        self._book: epub.EpubBook | None = None
        self._start_url = start_url
        self._chapter = chapter
        self._toc = []

        self._driver.get(start_url)
    
    def _form_book(self):
        """Creates book object and populates it with content from the start page."""
        title_page = TitlePage(self._driver, 10)
        self._book = epub.EpubBook()
        _id = parse_id(self._start_url)
        self._book.set_identifier(_id if _id else "default")
        self._book.set_title(title_page.title())
        self._book.set_language("ru")
        cover = retrieve_image(title_page.cover())
        if cover:
            self._book.set_cover("cover.jpg", cover)
            # self._book.spine = ["cover", "nav"]
        self._book.spine = ["nav"]
        title_page.to_chapter(self._chapter)

    def __enter__(self) -> tuple[webdriver.Chrome, epub.EpubBook]:
        self._form_book()
        return self._driver, self._book, self._toc
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self._driver.quit()
        if self._book:
            self._book.toc = tuple(self._toc)
            self._book.add_item(epub.EpubNcx())
            self._book.add_item(epub.EpubNav())
            clean_filename = sanitize_filepath(f"{self._book.title}.epub")
            epub.write_epub(clean_filename, self._book)


def main():
    """Entry point."""
    # check selenium
    update_selenium(SELENIUM_FOLDER)
    # getting arguments
    url = "https://ranobelib.me/ru/book/62850--akuyaku-reijo-wa-shomin-ni-totsugitai-novel"
    # doing something
    creator = BookCreator(url)
    with creator as (driver, book, toc):
        # while True:
        for _ in range(5):
            chapter_page = ChapterPage(driver, 5)
            title = chapter_page.title()
            content = ["<html><body>"]
            for elem in chapter_page.content():
                if elem.type == ElementType.Text:
                    content.append(f"<p>{elem.content}</p>")
                elif elem.type == ElementType.Image:
                    pass
            content.append("</html></body>")
            if len(content) > 2:
                chapter = epub.EpubHtml(
                    title=title,
                    file_name=f"{title}.xhtml",
                )
                chapter.content = "\n".join(content)
                book.add_item(chapter)
                book.spine.append(chapter)
                toc.append(chapter)
                print(f"[Info]: Finished chapter '{title}'")
            else:
                print(f"[Info]: Dropped chapter '{title}' - no content found")
            if not chapter_page.next_chapter():
                break
    # we are done
    print("[Info]: All done!")


if __name__ == "__main__":
    main()
