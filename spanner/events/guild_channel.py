import asyncio
import datetime
import logging

import discord
from discord.ext import bridge, commands

from spanner.cogs.channel_info import ChannelInfoCog
from spanner.share.utils import get_log_channel


class GuildChannelEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.guild_channel_events")
        self.log.setLevel(logging.DEBUG)

    async def wait_for_audit_log(self, channel: discord.abc.GuildChannel, action: discord.AuditLogAction):
        def the_check(e: discord.AuditLogEntry):
            if e.target == channel and e.action == action:
                return True
            return False

        if not channel.guild.me.guild_permissions.view_audit_log:
            return
        now = discord.utils.utcnow()
        after = now - datetime.timedelta(seconds=59)
        async for entry in channel.guild.audit_logs(after=after, action=action):
            if the_check(entry):
                return entry

        try:
            entry = await self.bot.wait_for("audit_log_entry", check=the_check, timeout=600)
            if not entry:
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            self.log.debug(
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a channel change.",
                channel.guild,
                channel,
            )
        else:
            return entry

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = await get_log_channel(self.bot, channel.guild.id, "server.channel.create")
        if log_channel is None:
            return

        cog = ChannelInfoCog(self.bot)
        embeds = await cog.get_channel_info(channel)
        embeds["Overview"].title = f"Channel created: {channel.name}"
        msg = await log_channel.send(embeds=list(embeds.values()))
        await asyncio.sleep(3)
        entry = await self.wait_for_audit_log(channel, discord.AuditLogAction.channel_create)
        if entry:
            embeds["Overview"].set_author(
                name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url
            )
            embeds["Overview"].set_footer(text="Details fetched from audit log.")
            if entry.reason:
                embeds["Overview"].add_field(name="Reason", value=entry.reason, inline=False)
        await msg.edit(embeds=list(embeds.values()))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = await get_log_channel(self.bot, channel.guild.id, "server.channel.delete")
        if log_channel is None:
            return

        cog = ChannelInfoCog(self.bot)
        embeds = await cog.get_channel_info(channel)
        for _embed in embeds.values():
            _embed.colour = discord.Colour.red()
        embeds["Overview"].title = f"Channel deleted: {channel.name}"
        msg = await log_channel.send(embeds=list(embeds.values()))
        await asyncio.sleep(3)
        entry = await self.wait_for_audit_log(channel, discord.AuditLogAction.channel_create)
        if entry:
            embeds["Overview"].set_author(
                name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url
            )
            embeds["Overview"].set_footer(text="Details fetched from audit log.")
            if entry.reason:
                embeds["Overview"].add_field(name="Reason", value=entry.reason, inline=False)
        await msg.edit(embeds=list(embeds.values()))


def setup(bot):
    bot.add_cog(GuildChannelEvents(bot))
