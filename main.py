import logging
from argparse import ArgumentParser
from pathlib import Path

import requests
from ebooklib import epub
from selenium import webdriver
from webdriver_auto_update.webdriver_manager import WebDriverManager

from pages import ChapterPage, ElementType, TitlePage
from utilities import get_book_id, sanitize_filepath

SELENIUM_FOLDER = "C:\\Programs\\Selenium"
CACHE_FOLDER = Path("cache/")

logger = logging.getLogger("parser")


def update_selenium(path: str):
    # Create an instance of WebDriverManager
    driver_manager = WebDriverManager(path)

    # Call the main method to manage chromedriver
    driver_manager.main()


def create_webdriver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    return webdriver.Chrome(options)


def retrieve_image(url: str):
    response = requests.get(url)
    if response.ok:
        return response.content
    return None


class BookCreator:
    def __init__(self, start_url: str, chapter: int | None = 0) -> None:
        self._driver = create_webdriver()
        self._book: epub.EpubBook | None = None
        self._start_url = start_url
        self._chapter = chapter
        self._toc = []

        self._driver.get(start_url)
    
    def _form_book(self):
        """Creates book object and populates it with content from the start page."""
        title_page = TitlePage(self._driver, 10)
        self._book = epub.EpubBook()
        _id = get_book_id(self._start_url)
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
    
    def __exit__(self, exc_type, exc_value, exc_tb) -> bool:
        self._driver.quit()
        if not self._book:
            return False
        self._book.toc = tuple(self._toc)
        self._book.add_item(epub.EpubNcx())
        self._book.add_item(epub.EpubNav())
        clean_filename = sanitize_filepath(f"{self._book.title}.epub")
        epub.write_epub(clean_filename, self._book)
        return True


def parse_arguments():
    parser = ArgumentParser(
        prog="RanobeLIB parser",
        description="As you expect",
    )
    parser.add_argument("url")
    parser.add_argument(
        "-f", "--from", type=int, default=None,
        help="From which chapter to start (number).")
    parser.add_argument(
        "-n", "--num", type=int, default=None,
        help="Number of chapters to parse.")
    return parser.parse_args()

def main():
    """Entry point."""
    # Setting logging
    logging.basicConfig(
        format="[%(levelname)s]: %(message)s",
        level=logging.CRITICAL,
    )
    logger.setLevel(logging.DEBUG)
    logging.addLevelName(logging.DEBUG, "Debg")
    logging.addLevelName(logging.INFO, "Info")
    logging.addLevelName(logging.WARN, "Warn")
    logging.addLevelName(logging.ERROR, "Erro")
    # getting arguments
    args = parse_arguments()
    url = args.url
    start_chapter = getattr(args, "from")  # because from is reserved keyword
    chapters_num = args.num or 1_000
    # check selenium
    update_selenium(SELENIUM_FOLDER)
    # doing something
    creator = BookCreator(url, start_chapter)
    with creator as (driver, book, toc):
        chapters = 0
        while chapters < chapters_num:
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
                logger.info("Finished chapter '%s'", title)
                chapters += 1
            else:
                logger.info("Dropped chapter '%s' - no content found", title)
            if not chapter_page.next_chapter():
                break
    # we are done
    logger.info("Parsed %d chapters", chapters)
    logger.info("All done!")


if __name__ == "__main__":
    main()
