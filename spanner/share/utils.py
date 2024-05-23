import textwrap
from typing import Any, Literal
from urllib.parse import urlparse

import discord
from discord.ext import commands, bridge

from .data import boolean_emojis
from .database import GuildLogFeatures

__all__ = [
    "get_bool_emoji",
    "first_line",
    "hyperlink",
    "pluralise",
    "humanise_bytes",
    "SilentCommandError",
    "get_log_channel"
]


class SilentCommandError(commands.CommandError):
    """A command error that, when handled will not send a generic error message in the global error handler.

    This should be used to suppress the default error message for a specific command, and instead allow the command
    to handle error messages itself, while still passing on a traceback to the global error handler."""
    def __init__(self, message: str, *args: Any, original: Exception | None = None):
        self.original: Exception = original or self
        super().__init__(message, *args)


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


async def get_log_channel(bot: bridge.Bot, guild_id: int, log_feature: str) -> discord.abc.Messageable | None:
    """
    Fetches the log channel for a guild, where the given log feature is enabled.

    :param bot: The bot instance
    :type bot: bridge.Bot
    :param guild_id: The guild ID
    :type guild_id: int
    :param log_feature: The log feature name
    :type log_feature: str
    :return: The log channel, if found and available
    :rtype: discord.abc.Messageable | None
    """
    log_feature = await GuildLogFeatures.get_or_none(
        guild_id=guild_id,
        name=log_feature
    )
    if not log_feature or log_feature.enabled is False:
        return

    await log_feature.fetch_related("guild")

    log_channel = bot.get_channel(log_feature.guild.log_channel)
    if not log_channel or not log_channel.can_send(discord.Embed, discord.File):
        return

    return log_channel
