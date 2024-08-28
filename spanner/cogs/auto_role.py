import discord
from discord.ext import commands

from spanner.share.database import GuildAuditLogEntry


class AutoRoleConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    auto_roles = discord.SlashCommandGroup(
        name="auto-roles",
        description="Manage auto roles for the server.",
        default_member_permissions=discord.Permissions(manage_guild=True, manage_roles=True),
    )

    @auto_roles.command(name="add")
    async def add_auto_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        """Add an auto role to the server."""
        await ctx.defer(ephemeral=True)
        config = await self._ensure_guild_config(ctx.guild_id)
        if role.id in config.auto_roles:
            return await ctx.respond(f"\N{CROSS MARK} {role.mention} is already an auto role.")
        config.auto_roles.append(role.id)
        await config.save()
        await GuildAuditLogEntryNew.generate(
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
            }
        )
        await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Added {role.mention} as an auto role.")
