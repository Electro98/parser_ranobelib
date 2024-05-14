import re
from dataclasses import dataclass, is_dataclass
from enum import StrEnum, auto
from functools import wraps
from logging import getLogger
from time import sleep
from typing import Any, Callable, Generic, Iterable, Type, TypeVar

T, V = TypeVar("T"), TypeVar("V")

logger = getLogger("parser.utils")


class ElementType(StrEnum):
    Text = auto()
    ImageLink = auto()
    ImageId = auto()


@dataclass
class Element:
    type: ElementType
    content: str


class Url:
    def __init__(self, url: str) -> None:
        self._url = url
    
    def __truediv__(self, other: str) -> "Url":
        return Url(f"{self._url.lstrip('/')}/{other}")

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(\'{self._url}\')"

    def args(self, **kwargs) -> str:
        return (
            f"{self._url.lstrip('/')}?"
            f"{'&'.join((f'{k}={v}' for k, v in kwargs.items()))}"
        )


class Seq(Generic[T]):
    """Generic class for simpler operation stacking."""
    def __init__(self, seq: Iterable[T]) -> None:
        self._seq = seq
    
    def map(self, func: Callable[[T], V]) -> "Seq[V]":
        return Seq(map(func, self._seq))

    def filter(self, func: Callable[[T], V] | None) -> "Seq[T]":
        return Seq(filter(func, self._seq))
    
    def collect(self, func: Callable[[Iterable[T]], V]) -> V:
        return func(self._seq)


def from_dict(dataclass: Type[T], data: dict[str, Any]) -> T:
    """Convert average non-nested dict to a dataclass instance."""
    if not is_dataclass(dataclass):
        raise TypeError(f"Expected dataclass type, got '{dataclass}'")
    fields = filter(dataclass.__match_args__.__contains__, data)
    return dataclass(**{field: data[field] for field in fields})


def get_book_name(book_url: str) -> str | None:
    # this part can be unnecessary (\?.+)?$
    match = re.search(r"book\/(\d+--[\w-]+)(\?.+)?$", book_url)
    return None if match is None else match.group(1)


def get_book_id(book_url: str) -> str | None:
    match = re.search(r"book\/(\d+)--", book_url)
    return None if match is None else match.group(1)


def deduplicate_name(names: list[str], name: str) -> str:
    if name not in names:
        return name
    number_striper = re.compile(r".*\((\d+)\)")
    try:
        number = (
            Seq(names)
                .map(number_striper.search)
                .filter(None)
                .map(lambda match: match.group(1))
                .map(int)
                .collect(max)
        )
    except ValueError:
        # There was no name with number yet
        number = 0
    return f"{name} ({number + 1})"


def sanitize_filepath(filename: str) -> str:
    return re.sub(r"[^\w_. -()]", "", filename)


def retry(func, retries: int = 5, sleep_time: float = 10.):
    @wraps(func)
    def wrapper(*args, **kwargs):
        exs = None
        for i in range(retries):
            try:
                result = func(*args, **kwargs)
            except Exception as _exs:
                result = None
                exs = _exs
            if result is not None:
                return result
            if i + 1 == retries:
                continue
            logger.debug("Function '%s' failed retrying in %.2f seconds",
                         func.__name__, sleep_time)
            sleep(sleep_time)
        logger.warning("Function '%s' failed to execute after %d attempts",
                       func.__name__, retries)
        if exs:
            raise exs
        return None
    
    return wrapper
