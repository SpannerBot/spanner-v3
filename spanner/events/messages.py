import io
import logging

import discord
from discord.ext import bridge, commands

from spanner.share.database import GuildConfig, GuildLogFeatures


class MessageEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.messages")

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


def setup(bot: bridge.Bot):
    bot.add_cog(MessageEvents(bot))
