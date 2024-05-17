from typing import Any, Literal
from urllib.parse import urlparse
import textwrap

from .data import boolean_emojis

__all__ = [
    "get_bool_emoji",
    "first_line",
    "hyperlink",
    "pluralise",
    "humanise_bytes",
]


def get_bool_emoji(value: Any) -> str:
    """Converts a given value into a boolean-based emoji (tick or cross).

    :param value: Any value that can be truthy
    :type value: Any
    :return: A boolean-based emoji
    :rtype: str
    """
    return boolean_emojis[bool(value)]


def first_line(text: str, max_length: int = 100, placeholder: str = "...") -> str:
    """Grabs the first line of a string and shortens it to a given length."""
    line = text.splitlines()[0]
    return textwrap.shorten(line, max_length, placeholder=placeholder)


def hyperlink(url: str, text: str = ...):
    """Generates a hyperlink, by default setting the display text to the URL's domain/host."""
    if text is ...:
        parsed = urlparse(url)
        text = parsed.hostname.lower()

    return f"[{text}]({url})"


def pluralise(word: str, value: int | float, *, precision: int | None = None):
    value = round(value, precision)
    if value == 1:
        return f"{value:,} {word}"
    return f"{value:,} {word}s"


def humanise_bytes(size_bytes: int, *, base: Literal[1000, 1024] = 1024) -> str:
    """Converts a given byte size into a human-readable format."""
    if size_bytes <= 1:
        return pluralise("byte", size_bytes)

    size_name = ("bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    if base == 1000:
        size_name = ("bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    size = size_bytes
    while size >= base:
        size /= base
        i += 1

    return f"{size:.2f} {size_name[i]}"
