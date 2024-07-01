import asyncio
import datetime
import logging

import discord
from discord.ext import bridge, commands

from spanner.share.utils import get_log_channel


class TimeoutEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.timeout")

    async def wait_for_audit_log(self, guild: discord.Guild, target: discord.Member, timed_out: bool = False):
        def the_check(e: discord.AuditLogEntry):
            if e.target == target and e.action == discord.AuditLogAction.member_update:
                return entry.target.timed_out == timed_out

        if not guild.me.guild_permissions.view_audit_log:
            return
        now = discord.utils.utcnow()
        after = now - datetime.timedelta(seconds=59)
        async for entry in guild.audit_logs(after=after, action=discord.AuditLogAction.member_update):
            if the_check(entry):
                return entry

        try:
            entry = await self.bot.wait_for("audit_log_entry", check=the_check, timeout=600)
            if not entry:
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            self.log.debug(
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a timeout.", guild, target
            )
        else:
            return entry

    async def on_member_timeout(self, member: discord.Member):
        self.log.debug("%r timed out in %r.", member, member.guild)
        if member.guild is None or member == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, member.guild.id, "member.timeout")
        if log_channel is None:
            return

        embed = discord.Embed(
            title="Member timed out!",
            colour=discord.Colour.red(),
            description=f"* Info: {member.mention} ({member.display_name}, `{member.id}`)\n"
            f"* Timed out until: {discord.utils.format_dt(member.communication_disabled_until, 'R')}",
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        cog = self.bot.get_cog("UserInfo")
        # noinspection PyUnresolvedReferences
        user_info_embed = (await cog.get_info(member))["Overview"]
        msg = await log_channel.send(embeds=[embed, user_info_embed])
        entry = await self.wait_for_audit_log(member.guild, member, timed_out=True)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Timeout details fetched from audit log.")
        await msg.edit(embeds=[embed, user_info_embed])

    async def on_member_timeout_expire(self, member: discord.Member):
        self.log.debug("%r time out expired in %r.", member, member.guild)
        if member.guild is None or member == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, member.guild.id, "member.timeout")
        if log_channel is None:
            return

        embed = discord.Embed(
            title="Member timeout expired!",
            colour=discord.Colour.red(),
            description=f"* Info: {member.mention} ({member.display_name}, `{member.id}`)",
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        cog = self.bot.get_cog("UserInfo")
        # noinspection PyUnresolvedReferences
        user_info_embed = (await cog.get_info(member))["Overview"]
        msg = await log_channel.send(embeds=[embed, user_info_embed])
        entry = await self.wait_for_audit_log(member.guild, member)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Timeout details fetched from audit log.")
        await msg.edit(embeds=[embed, user_info_embed])

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        self.log.debug(f"Got member update: {before!r} -> {after!r}")
        if before.timed_out == after.timed_out:
            return
        if after.timed_out:
            await self.on_member_timeout(after)
        else:
            await self.on_member_timeout_expire(after)


def setup(bot):
    bot.add_cog(TimeoutEvents(bot))
