import asyncio
import datetime
import logging

import discord
from discord.ext import bridge, commands

from spanner.share.utils import get_log_channel
from spanner.cogs.role_info import RoleInfo


class GuildRoleEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.guild_role_events")
        self.log.setLevel(logging.DEBUG)

    async def wait_for_audit_log(self, role: discord.Role, action: discord.AuditLogAction):
        def the_check(e: discord.AuditLogEntry):
            if e.target == role and e.action == action:
                return True
            return False

        if not role.guild.me.guild_permissions.view_audit_log:
            return
        now = discord.utils.utcnow()
        after = now - datetime.timedelta(seconds=59)
        async for entry in role.guild.audit_logs(after=after, action=action):
            if the_check(entry):
                return entry

        try:
            entry = await self.bot.wait_for("audit_log_entry", check=the_check, timeout=600)
            if not entry:
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            self.log.debug(
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a role change.",
                role.guild,
                role,
            )
        else:
            return entry

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel = await get_log_channel(self.bot, role.guild.id, "server.role.create")
        if log_channel is None:
            return

        embed = discord.Embed(title=f"Role created: {role.name}", colour=discord.Colour.red())

        embed2 = (await cog.get_role_info(after))["Overview"]

        msg = await log_channel.send(embeds=[embed, embed2])
        entry = await self.wait_for_audit_log(role, discord.AuditLogAction.role_create)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Details fetched from audit log.")
        await msg.edit(embeds=[embed, embed2])

    async def on_guild_role_permissions_update(self, before: discord.Role, after: discord.Role):
        log_channel = await get_log_channel(self.bot, after.guild.id, "server.role.permissions.edit")
        if log_channel is None:
            return

        site = "https://finitereality.github.io/permissions-calculator/?v={!s}"
        embed = discord.Embed(
            title=f"Role permissions updated: {after.name}",
            description="[Before]({}) | [After]({})".format(
                site.format(before.permissions),
                site.format(after.permissions),
            ),
            colour=discord.Colour.red(),
        )
        cog = RoleInfo(self.bot)
        role_info_embed = (await cog.get_role_info(after))["Overview"]
        msg = await log_channel.send(embeds=[embed, role_info_embed])
        entry = await self.wait_for_audit_log(after, discord.AuditLogAction.role_delete)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Details fetched from audit log.")
        await msg.edit(embeds=[embed, role_info_embed])

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.permissions != after.permissions:
            self.log.debug("Dispatching permissions update for %r->%r", before, after)
            await self.on_guild_role_permissions_update(before, after)
        changes = ("name", "color", "hoist", "icon", "mentionable", "tags", "unicode_emoji")
        for attr in changes:
            if getattr(before, attr) != getattr(after, attr):
                break
        else:
            self.log.debug("Got role update, %r -> %r, however nothing changed.", before, after)
            return  # no changes other than permissions
        log_channel = await get_log_channel(self.bot, after.guild.id, "server.role.edit")
        if log_channel is None:
            return

        embed = discord.Embed(title=f"Role deleted: {after.name}", colour=discord.Colour.red())
        embed2 = (await RoleInfo(self.bot).get_role_info(before))["Overview"]
        embed2.title = "[Before] " + embed2.title
        embed3 = (await RoleInfo(self.bot).get_role_info(after))["Overview"]
        embed3.title = "[After] " + embed3.title

        msg = await log_channel.send(embeds=[embed, embed2, embed3])
        entry = await self.wait_for_audit_log(after, discord.AuditLogAction.role_delete)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Details fetched from audit log.")
        await msg.edit(embeds=[embed, embed2, embed3])

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = await get_log_channel(self.bot, role.guild.id, "server.role.delete")
        if log_channel is None:
            return

        embed = discord.Embed(title=f"Role deleted: {role.name}", colour=discord.Colour.red())
        embed2 = (await RoleInfo(self.bot).get_role_info(role))["Overview"]

        msg = await log_channel.send(embeds=[embed, embed2])
        entry = await self.wait_for_audit_log(role, discord.AuditLogAction.role_delete)
        if entry is None:
            return

        embed.add_field(name="Reason", value=entry.reason or "No reason.")
        embed.set_author(name="Moderator: " + entry.user.display_name, icon_url=entry.user.display_avatar.url)
        embed.set_footer(text="Details fetched from audit log.")
        await msg.edit(embeds=[embed, embed2])


def setup(bot):
    bot.add_cog(GuildRoleEvents(bot))
