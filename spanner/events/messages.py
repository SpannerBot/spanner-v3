import io
import json
import logging
import os
import textwrap
from pathlib import Path

import discord
from discord.ext import bridge, commands
from jinja2 import Template

from spanner.share.database import GuildLogFeatures


class MessageEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.messages")

    def format_bulk_html(self):
        with open(Path.cwd() / "assets" / "bulk-delete.html") as f:
            template = Template(f.read())
        return template.render

    async def get_log_channel(self, guild_id: int, log_feature: str) -> discord.abc.Messageable | None:
        log_feature = await GuildLogFeatures.get_or_none(
            guild_id=guild_id,
            name=log_feature
        )
        if not log_feature or log_feature.enabled is False:
            return None
        await log_feature.fetch_related("guild")
        log_channel = self.bot.get_channel(log_feature.guild.log_channel)
        if not log_channel or not log_channel.can_send(discord.Embed, discord.File):
            return None
        return log_channel

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None or message.author == self.bot.user:
            return

        log_channel = await self.get_log_channel(message.guild.id, "message.delete")
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
        now = discord.utils.utcnow()
        embeds = {}
        for n, messages_chunk in enumerate(discord.utils.as_chunks(iter(messages), 10), start=1):
            files = []
            for message in messages_chunk:
                message_json = {
                    "content": message.content,
                    "embeds": [
                        embed.to_dict()
                        for embed in message.embeds
                    ]
                }
                message_json = json.dumps(
                    message_json,
                    indent=0,
                    separators=(",", ":"),
                    default=str
                )

                attachments = ("# Attachments:\n"
                               "Note: attachment URLs are not valid for very long after message deletion.\n")
                for n2, attachment in enumerate(message.attachments, start=1):
                    attachments += f"\n{n2}. {attachment.url}"
                attachments += "\n"
                content = textwrap.dedent(
                    f"""# Message Information

* Author: [{message.author.name} (`{message.author.id}`)]({message.author.jump_url})
* Channel: [#{message.channel.name} (`{message.channel.id}`)]({message.channel.jump_url})
* Message ID: {message.id}
* Created at: {message.created_at.isoformat()}
* Last edit: {message.edited_at.isoformat() if message.edited_at else "N/A"}
* Pinned: {message.pinned}
* Sent with TTS: {message.tts}

{attachments if message.attachments else ''}
# Data
You can import this data in an
[embed visualiser, such as this one](https://leovoel.github.io/embed-visualizer/).

```json
{message_json}
```"""
                )
                file = discord.File(
                    io.BytesIO(content.encode(errors="replace")),
                    filename=f"{os.urandom(1).hex()}_{message.author.display_name}"[:29] + ".md"
                )
                files.append(file)
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

        log_channel = await self.get_log_channel(messages[0].guild.id, "message.delete")
        if log_channel is None:
            return

        first_message = None
        for embed, files in embeds.items():
            m = await log_channel.send(embed=embed, files=files, reference=first_message)
            if not first_message:
                first_message = m

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
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
        unknown_messages = payload.message_ids.copy()
        for message in payload.cached_messages:
            if message.id in unknown_messages:
                unknown_messages.remove(message.id)

        if not unknown_messages:
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

        log_channel = await self.get_log_channel(guild.id, "message.delete.bulk")
        if log_channel is None:
            return
        await log_channel.send(embed=embed)


def setup(bot: bridge.Bot):
    bot.add_cog(MessageEvents(bot))
