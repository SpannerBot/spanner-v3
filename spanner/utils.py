from typing import Any
from .data import boolean_emojis

__all__ = ["get_bool_emoji"]


def get_bool_emoji(value: Any) -> str:
    """Converts a given value into a boolean-based emoji (tick or cross).

    :param value: Any value that can be truthy
    :type value: Any
    :return: A boolean-based emoji
    :rtype: str
    """
    return boolean_emojis[bool(value)]
