import asyncio
import collections
import datetime
import logging
import typing

import discord
from discord.ext import bridge, commands

from spanner.share.utils import get_log_channel


class LeaveEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.leave")
        self.leave_messages: typing.Deque[dict[discord.Member, discord.Message]] = collections.deque(maxlen=1000)

    async def wait_for_audit_log(self, guild: discord.Guild, target: discord.Member):
        if not guild.me.guild_permissions.view_audit_log:
            return
        now = discord.utils.utcnow()
        after = now - datetime.timedelta(minutes=2)
        async for entry in guild.audit_logs(after=after, action=discord.AuditLogAction.kick):
            if entry.target == target:
                return entry

        def the_check(e: discord.AuditLogEntry):
            return e.target == target and e.action == discord.AuditLogAction.kick

        try:
            entry = await self.bot.wait_for("audit_log_entry", check=the_check, timeout=600)
            if not entry:
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            self.log.debug(
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a kick.", guild, target
            )
        else:
            return entry

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self.log.debug("%r left %r.", member, member.guild)
        if member.guild is None or member == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, member.guild.id, "member.leave")
        if log_channel is None:
            return

        embed = discord.Embed(
            title="Member left!",
            description=f"There are now {member.guild.member_count:,} members in the server.",
            colour=discord.Colour.blue(),
            timestamp=discord.utils.utcnow(),
        )
        cog = self.bot.get_cog("UserInfo")
        # noinspection PyUnresolvedReferences
        user_info_embed = (await cog.get_member_info(member))["Overview"]
        embed.set_thumbnail(url=member.display_avatar.url)
        message = await log_channel.send(embeds=[embed, user_info_embed])
        entry = await self.wait_for_audit_log(member.guild, member)
        self.leave_messages.append({member: message})
        if entry:
            embed.title = "Member kicked!"
            embed.colour = discord.Colour.gold()
            embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
            embed.set_footer(text="Kick details fetched from audit log.")
            if entry.reason:
                embed.add_field(name="Reason", value=entry.reason, inline=False)
            await message.edit(embeds=[embed, user_info_embed])

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        await asyncio.sleep(60)
        for item in self.leave_messages:
            if item.get(user):
                if list(item.keys())[0].guild != guild:
                    continue
                message = item[user]
                e = discord.utils.utcnow() + datetime.timedelta(seconds=60)
                await message.edit(
                    content=f"This message will self-destruct {discord.utils.format_dt(e, 'R')}.",
                    delete_after=60,
                    embeds=[
                        *message.embeds,
                        discord.Embed(
                            description="This user was actually banned. If you have the `member.ban` feature enabled,"
                            " a ban log will be sent shortly."
                        ),
                    ],
                )
                self.leave_messages.remove(item)


def setup(bot: bridge.Bot):
    bot.add_cog(LeaveEvents(bot))
