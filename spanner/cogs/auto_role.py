import discord
from fnmatch import fnmatch
from discord.ext import commands
from tortoise.transactions import in_transaction
from spanner.share.database import GuildAuditLogEntry, AutoRole
from spanner.share.views import ConfirmView


class AutoRoleConfig(commands.Cog):
    MODERATOR_PERMISSIONS = (
        "kick_members",
        "ban_members",
        "manage_*",
        "moderate_members",
        "create_events",
    )
    def __init__(self, bot):
        self.bot = bot

    auto_roles_command = discord.SlashCommandGroup(
        name="auto-roles",
        description="Manage auto roles for the server.",
        contexts={discord.InteractionContextType.guild},
        default_member_permissions=discord.Permissions(manage_guild=True, manage_roles=True),
    )

    @auto_roles_command.command(name="add")
    async def add_auto_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        """Add an auto role to the server."""
        await ctx.defer(ephemeral=True)

        async with in_transaction() as conn:
            if await AutoRole.get_or_none(role_id=role.id):
                return await ctx.respond(f"\N{CROSS MARK} {role.mention} is already an auto role.")
            elif (await AutoRole.filter(guild_id=ctx.guild_id).count()) >= 25:
                return await ctx.respond("\N{CROSS MARK} You can only have up to 25 auto roles.")
            elif role.managed:
                return await ctx.respond("\N{CROSS MARK} You cannot add managed roles as auto roles.")
            elif role >= ctx.guild.me.top_role:
                return await ctx.respond("\N{CROSS MARK} This role is above my top role, I cannot assign it.")
            elif role >= ctx.author.top_role:
                return await ctx.respond("\N{CROSS MARK} This role is above your top role, you cannot assign it.")

            dangerous = []
            for key, value in dict(role.permissions).items():
                if any((fnmatch(key, perm_name) for perm_name in self.MODERATOR_PERMISSIONS)) and value is True:
                    dangerous.append(key)

            if dangerous:
                confirm = ConfirmView(
                    ctx.user,
                    title="This role seems to dangerous permissions.",
                    question="The following permissions are enabled for this role, which may be dangerous: {}\n"
                             "Are you sure you want to add this role as an auto role?".format(", ".join(dangerous)),
                    timeout=60
                )
                res, ok = await confirm.ask(ctx, False)
                if not ok:
                    return await res.edit(content="\N{CROSS MARK} Action cancelled.")
                await res.delete(delay=0.01)

            await AutoRole.create(
                guild_id=ctx.guild_id,
                role_id=role.id,
                using_db=conn,
            )
            await GuildAuditLogEntry.generate(
                ctx.guild_id,
                ctx.user,
                "auto_roles",
                "action",
                f"Added role {role.id} ({role.name}) to the auto roles.",
                metadata={
                    "action.historical": "added",
                    "role": {
                        "id": str(role.id),
                        "name": str(role.name),
                        "color": role.color.value,
                        "position": role.position,
                        "permissions": role.permissions.value,
                        "mentionable": role.mentionable,
                        "hoist": role.hoist,
                    }
                },
                using_db=conn,
            )
            await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Added {role.mention} as an auto role.")

    @auto_roles_command.command(name="list")
    async def list_auto_roles(self, ctx: discord.ApplicationContext):
        """List all auto roles for the server."""
        await ctx.defer(ephemeral=True)

        async with in_transaction() as conn:
            auto_roles: list[AutoRole] = await AutoRole.filter(guild_id=ctx.guild_id)
            if not auto_roles:
                return await ctx.respond("No auto roles have been configured for this server.")

            resolved_roles: list[discord.Role] = []
            for entry in auto_roles:
                role = ctx.guild.get_role(entry.role_id)
                if role:
                    resolved_roles.append(role)
                else:
                    await entry.delete(using_db=conn)
                    await GuildAuditLogEntry.generate(
                        ctx.guild_id,
                        self.bot.user,
                        "auto_roles",
                        "remove",
                        f"Removed role {entry.role_id} from the auto roles (role no longer exists).",
                        metadata={
                            "action.historical": "removed",
                            "role": {
                                "id": str(entry.role_id),
                            }
                        },
                        using_db=conn,
                    )
            await ctx.respond(
                embed=discord.Embed(
                    title="Auto roles:",
                    description=", ".join(role.mention for role in resolved_roles),
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow(),
                    footer=discord.EmbedFooter(text=f"{len(resolved_roles)}/25")
                )
            )

    @auto_roles_command.command(name="remove")
    async def remove_auto_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        """Remove an auto role from the server."""
        await ctx.defer(ephemeral=True)

        async with in_transaction() as conn:
            auto_role: AutoRole = await AutoRole.get_or_none(role_id=role.id)
            if not auto_role:
                return await ctx.respond(f"\N{CROSS MARK} {role.mention} is not an auto role.")
            await auto_role.delete(using_db=conn)
            await GuildAuditLogEntry.generate(
                ctx.guild_id,
                ctx.user,
                "auto_roles",
                "remove",
                f"Removed role {role.id} ({role.name}) from the auto roles.",
                metadata={
                    "action.historical": "removed",
                    "role": {
                        "id": str(role.id),
                        "name": str(role.name),
                        "color": role.color.value,
                        "position": role.position,
                        "permissions": role.permissions.value,
                        "mentionable": role.mentionable,
                        "hoist": role.hoist,
                    }
                },
                using_db=conn,
            )
            await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Removed {role.mention} from the auto roles.")

    @auto_roles_command.command(name="clear")
    async def clear_auto_roles(self, ctx: discord.ApplicationContext):
        """Clear all auto roles for the server."""
        await ctx.defer(ephemeral=True)

        async with in_transaction() as conn:
            auto_roles: list[AutoRole] = await AutoRole.filter(guild_id=ctx.guild_id)
            if not auto_roles:
                return await ctx.respond("No auto roles have been configured for this server.")

            msg, ok = await ConfirmView(ctx.user, "This action is irreversible!").ask(ctx, False)
            if not ok:
                return await msg.edit(content="\N{CROSS MARK} Aborted.")
            await AutoRole.filter(guild_id=ctx.guild_id).delete()
            await GuildAuditLogEntry.generate(
                ctx.guild_id,
                ctx.user,
                "auto_roles",
                "clear",
                "Cleared all auto roles for the server.",
                metadata={
                    "action.historical": "cleared",
                    "old": {
                        "roles": [str(entry.role_id) for entry in auto_roles],
                    }
                },
                using_db=conn,
            )
            await msg.edit("\N{WHITE HEAVY CHECK MARK} Cleared all auto roles for the server.")

    async def _add_auto_roles(self, member: discord.Member):
        auto_roles = await AutoRole.filter(guild_id=member.guild.id)
        if not auto_roles:
            return
        roles = [member.guild.get_role(role.role_id) for role in auto_roles]
        roles = list(filter(None, roles))
        roles = list(filter(lambda r: r < member.guild.me.top_role, roles))
        roles = list(sorted(roles, reverse=True))
        await member.add_roles(*roles, reason="Auto roles")
        await GuildAuditLogEntry.generate(
            member.guild.id,
            self.bot.user,
            "auto_roles",
            "action",
            f"Auto assigned roles to {member.id} ({member})",
            metadata={
                "action.historical": "auto_assigned",
                "member": {
                    "id": str(member.id),
                    "name": str(member),
                },
                "roles": [str(role.id) for role in roles],
            }
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        if member.pending:
            return  # assign later
        await self._add_auto_roles(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot:
            return
        if before.pending is False:
            return
        if after.pending is True:
            return
        if after.top_role >= after.guild.me.top_role:
            return

        await self._add_auto_roles(after)


def setup(bot):
    bot.add_cog(AutoRoleConfig(bot))
