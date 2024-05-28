import asyncio
import io
import json
import logging
import re
import textwrap
from base64 import b64encode
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import discord
from discord.ext import bridge, commands
from jinja2 import Template

from .data import boolean_emojis
from .database import GuildLogFeatures

__all__ = [
    "get_bool_emoji",
    "first_line",
    "hyperlink",
    "pluralise",
    "humanise_bytes",
    "SilentCommandError",
    "get_log_channel",
    "format_html",
    "format_template",
]
log = logging.getLogger(__name__)


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
    lfn = log_feature
    log_feature = await GuildLogFeatures.get_or_none(guild_id=guild_id, name=log_feature)
    if not log_feature or log_feature.enabled is False:
        log.debug("%r does not have the feature %r enabled.", guild_id, lfn)
        return

    await log_feature.fetch_related("guild")

    log_channel = bot.get_channel(log_feature.guild.log_channel)
    if not log_channel or not log_channel.can_send(discord.Embed, discord.File):
        log.debug("%rs log channel is missing or blocked.", guild_id)
        return
    log.debug("%rs log channel is %r.", log_channel.name, log_channel)
    return log_channel


def _get_css(minify: bool = False) -> str:
    with open("assets/style.css") as f:
        t = f.read()
    if not minify:
        return t
    t = re.sub(r"\s+", "", t)
    return t


async def format_html(message: discord.Message):
    with open(Path.cwd() / "assets" / "bulk-delete.html") as f:
        template = Template(f.read())
    embeds = [embed.to_dict() for embed in message.embeds]
    for n, embed in enumerate(embeds, start=1):
        embed.setdefault("title", "Untitled Embed %d" % n)
    embeds = [json.dumps(embed, separators=(",", ":"), default=str, ensure_ascii=False) for embed in embeds]

    async def download_attachment(att: discord.Attachment) -> tuple[discord.Attachment, str] | tuple[None, None]:
        bio = io.BytesIO()
        try:
            log.info("Downloading %r", att)
            await att.save(bio)
        except discord.HTTPException as e:
            log.warning("Failed to download %r: %s", att, e, exc_info=e)
            return None, None
        else:
            bio.seek(0)
            return att, b64encode(bio.getvalue()).decode()

    attachments = {}
    tasks = []
    for attachment in message.attachments:
        if attachment.size <= 1024 * 1024 * 2:
            log.debug("Adding %r to the download queue.", attachment)
            tasks.append(download_attachment(attachment))
    if tasks:
        log.debug("Waiting for %d downloads", len(tasks))
        for result in await asyncio.gather(*tasks):
            _attachment, _data = result
            if not _attachment:
                continue
            attachments[_attachment.filename] = _data
        log.debug("Downloads finished.")

    kwargs = dict(
        message=message,
        created_at=message.created_at.isoformat(),
        edited_at=message.edited_at.isoformat() if message.edited_at else "N/A",
        embeds=embeds,
        cached_attachments=attachments,
        now=discord.utils.utcnow().isoformat(),
        css=_get_css(True),
    )
    r = template.render(**kwargs)
    if len(r) >= (message.guild.filesize_limit - 8192):
        log.warning("Rendered template was too big, removing cached attachments.")
        kwargs["cached_attachments"] = {}
        return template.render(**kwargs)
    return r


def format_template(template: str, **kwargs) -> str:
    p = Path("assets") / template
    if p.exists():
        template = p.read_text()
    kwargs.setdefault("css", _get_css(True))
    return Template(template).render(**kwargs)
