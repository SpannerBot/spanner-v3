import asyncio
import datetime
import logging

import discord
from discord.ext import bridge, commands
from typing import Iterable

from spanner.share.utils import get_log_channel


class RoleEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.role_events")

    async def wait_for_audit_log(
            self,
            guild: discord.Guild,
            target: discord.Member,
            before: Iterable[discord.Role] | None = None,
            after: Iterable[discord.Role] | None = None
    ):
        def the_check(e: discord.AuditLogEntry):
            if e.target == target and e.action == discord.AuditLogAction.member_role_update:
                nonlocal before, after
                if before:
                    # Check if any of the roles in `before` are in the `e.before` list
                    if any(role.id in [r.id for r in e.before] for role in before):
                        return True
                if after:
                    # Check if any of the roles in `after` are in the `e.after` list
                    if any(role.id in [r.id for r in e.after] for role in after):
                        return True

        if not guild.me.guild_permissions.view_audit_log:
            return
        now = discord.utils.utcnow()
        after = now - datetime.timedelta(seconds=59)
        async for entry in guild.audit_logs(after=after, action=discord.AuditLogAction.member_role_update):
            if the_check(entry):
                return entry

        try:
            entry = await self.bot.wait_for("audit_log_entry", check=the_check, timeout=600)
            if not entry:
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            self.log.debug(
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a role change.",
                guild,
                target
            )
        else:
            return entry

    @staticmethod
    def role_list(roles: Iterable[discord.Role], max_length: int = 1024) -> str:
        """Generates an automatically truncated role list string."""
        result = ", ".join(role.mention for role in sorted(roles, reverse=True))
        n = 0
        while len(result) > max_length:
            n += 1
            result = ", ".join(role.mention for role in sorted(roles, reverse=True)[:-n])
            result += ", *and {:,} more...*".format(n)
        return result

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        self.log.debug(f"Got member update: {before!r} -> {after!r}")
        if before.timed_out == after.timed_out:
            return

        roles_added = set(after.roles) - set(before.roles)
        roles_removed = set(before.roles) - set(after.roles)

        actions = []
        if roles_added:
            actions.append("gained")
        if roles_removed:
            actions.append("lost")
        r_word = "roles" if (sum(roles_removed) + sum(roles_added)) > 1 else "role"
        embed = discord.Embed(
            title=f"{after.display_name} {', '.join(actions)} {len(roles_added) + len(roles_removed):,} {r_word}:",
            colour=discord.Colour.blurple(),
            timestamp=discord.utils.utcnow()
        )
        if roles_added:
            embed.add_field(
                name="Roles Added:",
                value=self.role_list(roles_added),
                inline=False
            )
        if roles_removed:
            embed.add_field(
                name="Roles Removed:",
                value=self.role_list(roles_removed),
                inline=False
            )

        log_channel = await get_log_channel(self.bot, after.guild.id, "member.roles.update")
        if log_channel is None:
            return
        embed.set_thumbnail(url=after.display_avatar.url)
        msg = await log_channel.send(embed=embed)
        entry = await self.wait_for_audit_log(after.guild, after)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Timeout details fetched from audit log.")
        await msg.edit(embed=embed)


def setup(bot):
    bot.add_cog(RoleEvents(bot))
