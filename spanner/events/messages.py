import io
import json
import logging
import os
import textwrap
from pathlib import Path

import discord
from discord.ext import bridge, commands

from spanner.share.utils import format_html, get_log_channel
from spanner.share.database import GuildLogFeatures


class MessageEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.messages")

    async def get_log_channel(self, *args):
        return await get_log_channel(self.bot, *args)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        self.log.debug("Got deleted message event: %r", message)
        if message.guild is None or message.author == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, message.guild.id, "message.delete")
        if log_channel is None:
            return

        embed = discord.Embed(
            title=f"Message deleted in #{message.channel.name}:",
            description=message.content or '*No content.*',
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url,
            url=message.author.jump_url
        )
        embed.add_field(
            name="Info:",
            value=f"Author: {message.author.mention} (`{message.author.id}`)\n"
                  f"Created: {discord.utils.format_dt(message.created_at, 'R')}\n"
                  f"Was pinned: {message.pinned}",
        )
        embeds = [embed]
        if message.embeds:
            for embed in message.embeds[:9]:
                embeds.append(embed)
        await log_channel.send(embeds=embeds)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        self.log.debug("Got bulk delete event: %r", messages)
        log_channel = await self.get_log_channel(messages[0].guild.id, "message.delete")
        if log_channel is None:
            return

        now = discord.utils.utcnow()
        embeds = {}
        for n, messages_chunk in enumerate(discord.utils.as_chunks(iter(messages), 10), start=1):
            files = []
            for message in messages_chunk:
                html = await format_html(message)
                if html:
                    files.append(
                        discord.File(
                            io.BytesIO(html.encode()),
                            filename=f"{message.author.display_name}-{message.id}"[:27] + ".html",
                            description="The message content in HTML format."
                        )
                    )
            embed = discord.Embed(
                title=f"{len(messages):,} messages deleted in {messages[0].channel.name}:",
                description="Check the files for more details.",
                color=discord.Color.red(),
                timestamp=now
            )
            embed.set_footer(
                text=f"Chunk {n}/{len(messages_chunk)}",
                icon_url=self.bot.user.display_avatar.url
            )
            embeds[embed] = files

        first_message = None
        for embed, files in embeds.items():
            m = await log_channel.send(embed=embed, files=files, reference=first_message)
            if not first_message:
                first_message = m

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        self.log.debug("Got message edit event: %r -> %r", before, after)
        if after.guild is None or after.author == self.bot.user:
            return
        if after.content == before.content:
            return
        log_channel = await self.get_log_channel(after.guild.id, "message.edit")
        if log_channel is None:
            return

        embed = discord.Embed(
            title=f"[click to jump] Message edited in #{after.channel.name}:",
            color=discord.Color.red(),
            timestamp=after.edited_at or discord.utils.utcnow(),
            url=after.jump_url
        )
        embed.set_author(
            name=after.author.display_name,
            icon_url=after.author.display_avatar.url,
            url=after.author.jump_url
        )
        embed.add_field(
            name="Info:",
            value=f"Author: {after.author.mention} (`{after.author.id}`)\n"
                  f"Created: {discord.utils.format_dt(after.created_at, 'R')}\n"
                  f"Edited: {discord.utils.format_dt(after.edited_at, 'R')}\n"
                  f"Tip: You can right-click on [this message]({after.jump_url}) and click 'message info' to see more.",
        )
        files = []
        if before.content != after.content:
            if len(before.content) > 1024:
                files.append(
                    discord.File(
                        io.BytesIO(before.content.encode(errors="replace")),
                        filename="before.txt",
                        description="The content of the message before it was edited."
                    )
                )
                embed.add_field(
                    name="Before:",
                    value="The content of the message before it was edited is too long to display here. "
                          "Please see the attached file: `before.txt`.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Before:",
                    value=before.content,
                    inline=False
                )
            if len(after.content) > 1024:
                files.append(
                    discord.File(
                        io.BytesIO(after.content.encode(errors="replace")),
                        filename="after.txt",
                        description="The content of the message after it was edited."
                    )
                )
                embed.add_field(
                    name="After:",
                    value="The content of the message after it was edited is too long to display here. "
                          "Please see the attached file: `after.txt`."
                )
            else:
                embed.add_field(
                    name="After:",
                    value=after.content
                )
        await log_channel.send(embed=embed, files=files)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        self.log.debug("Got raw bulk delete event: %r", payload)
        log_channel = await self.get_log_channel(payload.guild_id, "message.delete.bulk")
        if log_channel is None:
            return

        unknown_messages = payload.message_ids.copy()
        for message in payload.cached_messages:
            if message.id in unknown_messages:
                self.log.debug("[raw bulk] Found a known message: %r", message.id)
                unknown_messages.remove(message.id)

        if not unknown_messages:
            self.log.debug("[raw bulk] There were no unknown messages, event handled entirely by cache.")
            return

        channel = self.bot.get_channel(payload.channel_id)
        guild = channel.guild
        embed = discord.Embed(
            title=f"{len(unknown_messages):,} unknown messages deleted in #{channel.name}:",
            description=f"{len(payload.message_ids):,} messages were deleted, "
                        f"but I did not have {len(unknown_messages):,} of them saved.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        if len(unknown_messages) != len(payload.message_ids):
            known = len(payload.message_ids) - len(unknown_messages)
            embed.description += f"\nYou may receive a message containing {known:,} known messages."

        await log_channel.send(embed=embed)


def setup(bot: bridge.Bot):
    bot.add_cog(MessageEvents(bot))
