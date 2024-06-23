import asyncio
import datetime
import logging

import discord
from discord.ext import bridge, commands

from spanner.share.utils import get_log_channel


class NicknameChangeEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.nickname_change")

    async def wait_for_audit_log(self, guild: discord.Guild, target: discord.Member, nick: str | None):
        def the_check(e: discord.AuditLogEntry):
            if e.target == target and e.action == discord.AuditLogAction.member_update:
                return entry.target.nick == nick

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
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a nick change.",
                guild,
                target,
            )
        else:
            return entry

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        self.log.debug("%r update %r -> %r.", before, before.guild, after)
        if before.guild is None or before == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, before.guild.id, "member.nickname-change")
        if log_channel is None:
            return

        if before.nick != after.nick:
            embed = discord.Embed(
                title="Member changed nickname!",
                colour=discord.Colour.blue(),
                description=f"* Before: {discord.utils.escape_markdown(before.nick or 'N/A')}\n"
                f"* After: {discord.utils.escape_markdown(after.nick or 'N/A')}\n",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            msg = await log_channel.send(embed=embed)
            entry = await self.wait_for_audit_log(before.guild, after, after.nick)
            if entry:
                embed.set_author(name=f"Moderator: {entry.user}", icon_url=entry.user.display_avatar.url)
                embed.set_footer(text="Nickname change details fetched from audit log.")
                await msg.edit(embed=embed)


def setup(bot: bridge.Bot):
    bot.add_cog(NicknameChangeEvents(bot))
