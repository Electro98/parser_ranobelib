import logging
from argparse import ArgumentParser
from pathlib import Path
from time import time

import requests
from ebooklib import epub

from api import (BookAPI, ChapterInfo, parse_chapter, parse_chapters,
                 parse_manga_info)
from utilities import ElementType, deduplicate_name, sanitize_filepath

CACHE_FOLDER = Path("cache/")

logger = logging.getLogger("parser")


def retrieve_image(url: str) -> bytes | None:
    response = requests.get(url)
    if response.ok:
        return response.content
    return None


class BookCreator:
    def __init__(self, start_url: str, chapter: int | None = None) -> None:
        self._book: epub.EpubBook | None = None
        self._api = BookAPI(start_url)
        self._chapter = chapter - 1 if chapter else 0
        self._toc = []

    def _form_book(self):
        """Creates book object and populates it with content from the start page."""
        book_info = parse_manga_info(self._api.manga_link())
        logger.debug("Retrieved information about the book")
        self._book = epub.EpubBook()
        self._book.set_identifier(str(book_info.id))
        self._book.set_title(book_info.rus_name)
        self._book.set_language("ru")
        cover = retrieve_image(book_info.cover_img)
        if cover:
            self._book.set_cover("cover.jpg", cover)
            # self._book.spine = ["cover", "nav"]
            logger.info("Added cover image!")
        else:
            logger.debug("Failed to retrieve cover image")
        self._book.spine = ["nav"]

    def _to_chapter(self):
        self._chapters = parse_chapters(self._api.chapters_link())
        if self._chapters is None:
            raise ValueError("Failed to parse chapters!") 
        elif len(self._chapters) <= self._chapter:
            logger.info("There less chapters than was expected!")
            logger.info("Starting from 1 chapter!")
        else:
            self._chapters = self._chapters[self._chapter:]

    def __enter__(self) -> tuple[BookAPI, epub.EpubBook, list, list[ChapterInfo]]:
        self._form_book()
        self._to_chapter()
        return self._api, self._book, self._toc, self._chapters

    def __exit__(self, exc_type, exc_value, exc_tb) -> bool:
        if not self._book:
            return False
        if exc_tb:
            logger.debug("Caught exs: %s %s", exc_type, exc_value)
        logger.info("Starting saving book")
        self._book.toc = tuple(self._toc)
        self._book.add_item(epub.EpubNcx())
        self._book.add_item(epub.EpubNav())
        clean_filename = sanitize_filepath(f"{self._book.title}.epub")
        epub.write_epub(clean_filename, self._book)
        logger.debug("Saved book '%s'", self._book.title)
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
    # doing something
    start_time = time()
    creator = BookCreator(url, start_chapter)
    logger.debug("Starting parsing process")
    parsed_chapters = 0
    with creator as (api, book, toc, chapters):
        chapter_names = []
        content_hashes = []
        for chapter_info in chapters[:chapters_num]:
            chapter = parse_chapter(api.chapter_link(chapter_info))
            content = ["<html><body>"]
            for elem in chapter.content:
                if elem.type == ElementType.Text:
                    content.append(f"<p>{elem.content}</p>")
                elif elem.type == ElementType.ImageId:
                    pass
                elif elem.type == ElementType.ImageLink:
                    pass
            content.append("</html></body>")
            if len(content) > 2:
                title = deduplicate_name(chapter_names, chapter.name)
                content = "\n".join(content)
                content_hash = hash(content)
                if content_hash in content_hashes:
                    logger.warn("Found chapter duplicate '%s' - removing", title)
                    continue
                book_chapter = epub.EpubHtml(
                    title=title,
                    file_name=f"{title}.xhtml",
                )
                book_chapter.content = content
                book.add_item(book_chapter)
                book.spine.append(book_chapter)
                toc.append(book_chapter)
                chapter_names.append(title)
                content_hashes.append(content_hash)
                logger.info("Finished chapter %s vol %s '%s'",
                            chapter.number, chapter.volume, title)
                parsed_chapters += 1
            else:
                logger.info("Dropped chapter %s vol %s '%s' - no content found",
                            chapter.number, chapter.volume, title)
    # we are done
    result_time = time() - start_time
    logger.info("Parsed %d chapters", parsed_chapters)
    logger.debug("Time: %d minutes %.2f seconds", result_time // 60, result_time % 60)
    logger.info("All done!")


if __name__ == "__main__":
    main()
