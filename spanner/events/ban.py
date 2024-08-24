import logging

import discord
from discord.ext import bridge, commands

from spanner.cogs.user_info import UserInfo
from spanner.share.utils import get_log_channel


class BanEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.ban")
        self.awaiting_audit_log = {}

    @commands.Cog.listener()
    async def on_audit_log_entry(self, entry: discord.AuditLogEntry):
        for values in self.awaiting_audit_log.copy().values():
            if values["target"] == entry.target:
                if values["guild"] == entry["guild"]:
                    if values["type"] == "ban" and entry.action == discord.AuditLogAction.ban:
                        values["embed"].set_author(
                            name="Moderator: %s" % entry.user.display_name, icon_url=entry.user.display_avatar.url
                        )
                        values["embed"].set_footer(text="Ban details fetched from audit log.")
                        if entry.reason:
                            values["embed"].add_field(name="Reason", value=entry.reason[:1024])
                        try:
                            await values["message"].edit(embed=values["embed"])
                        except discord.HTTPException:
                            pass
                        self.awaiting_audit_log.pop(values["message"].user_id)
                    elif values["type"] == "unban" and entry.action == discord.AuditLogAction.unban:
                        values["embed"].set_author(
                            name="Moderator: %s" % entry.user.display_name, icon_url=entry.user.display_avatar.url
                        )
                        values["embed"].set_footer(text="Unban details fetched from audit log.")
                        if entry.reason:
                            values["embed"].add_field(name="Reason", value=entry.reason[:1024])
                        try:
                            await values["message"].edit(embed=values["embed"])
                        except discord.HTTPException:
                            pass
                        self.awaiting_audit_log.pop(values["message"].user_id)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        self.log.info("%r was banned in %r.", user, guild)
        if guild is None or user == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, guild.id, "member.ban")
        if log_channel is None:
            return

        if isinstance(user, discord.Member):
            embed = discord.Embed(
                title="Member Banned",
                colour=discord.Colour.red(),
                description=f"* Info: {user.mention} ({user.display_name}, `{user.id}`)\n"
                f"* Created: {discord.utils.format_dt(user.created_at, 'R')}\n"
                f"* Joined: {discord.utils.format_dt(user.joined_at, 'R')}\n",
                timestamp=discord.utils.utcnow(),
            )
            roles = user.roles
            for role in roles.copy():
                if role.permissions == guild.default_role.permissions:
                    roles.remove(role)
                elif not role.permissions.value:
                    roles.remove(role)
            if roles:
                joined = ", ".join([role.mention for role in roles])
                if len(joined) > 1024:
                    joined = ", ".join([role.mention for role in roles[:10]])
                    joined += f"... and {len(roles) - 10} more."
                embed.add_field(name="Roles", value=joined)
        else:
            embed = discord.Embed(
                title="User Banned",
                colour=discord.Colour.red(),
                description=f"* Info: {user.mention} (`{user.id}`)\n"
                f"* Created: {discord.utils.format_dt(user.created_at, 'R')}\n"
                f"*User was not in the server when they were banned.*",
                timestamp=discord.utils.utcnow(),
            )

        found_reason = False
        if guild.me.guild_permissions.view_audit_log:
            async for audit_log in guild.audit_logs(action=discord.AuditLogAction.ban):
                if audit_log.target == user:
                    if audit_log.reason:
                        embed.add_field(name="Reason", value=audit_log.reason[:1024])
                    embed.set_author(
                        name="Moderator: %s" % audit_log.user.display_name, icon_url=audit_log.user.display_avatar.url
                    )
                    embed.set_footer(text="Ban details fetched from audit log.")
                    found_reason = False
                    break
        else:
            embed.set_footer(text="Ban details could not be fetched from audit log - missing permissions.")
        embed.set_thumbnail(url=user.display_avatar.url)
        cog = UserInfo(self.bot)
        user_info_embed = (await cog.get_info(user))["Overview"]
        msg = await log_channel.send(embeds=[embed, user_info_embed])
        if not found_reason:
            self.awaiting_audit_log[msg.id] = {
                "target": user,
                "guild": guild,
                "message": msg,
                "embed": embed,
                "type": "ban",
            }

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        self.log.info("%r was unbanned in %r.", user, guild)
        if guild is None or user == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, guild.id, "member.unban")
        if log_channel is None:
            return

        embed = discord.Embed(
            title="User Unbanned",
            colour=discord.Colour.green(),
            description=f"* Info: {user.mention} (`{user.id}`)\n"
            f"* Created: {discord.utils.format_dt(user.created_at, 'R')}\n",
            timestamp=discord.utils.utcnow(),
        )

        found_reason = False
        if guild.me.guild_permissions.view_audit_log:
            async for audit_log in guild.audit_logs(action=discord.AuditLogAction.unban):
                if audit_log.target == user:
                    if audit_log.reason:
                        embed.add_field(name="Reason", value=audit_log.reason[:1024])
                    embed.set_author(
                        name="Moderator: %s" % audit_log.user.display_name, icon_url=audit_log.user.display_avatar.url
                    )
                    embed.set_footer(text="Unban details fetched from audit log.")
                    found_reason = False
                    break
        else:
            embed.set_footer(text="Unban details could not be fetched from audit log - missing permissions.")

        embed.set_thumbnail(url=user.display_avatar.url)
        cog = UserInfo(self.bot)
        user_info_embed = (await cog.get_info(user))["Overview"]
        msg = await log_channel.send(embeds=[embed, user_info_embed])
        if not found_reason:
            self.awaiting_audit_log[msg.id] = {
                "target": user,
                "guild": guild,
                "message": msg,
                "embed": embed,
                "type": "unban",
            }


def setup(bot: bridge.Bot):
    bot.add_cog(BanEvents(bot))
