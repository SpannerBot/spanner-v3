from typing import Any
from urllib.parse import urlparse
import textwrap

from .data import boolean_emojis

__all__ = [
    "get_bool_emoji",
    "first_line",
    "hyperlink"
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
