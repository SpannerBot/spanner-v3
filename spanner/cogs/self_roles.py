import logging

import discord

from discord.ext import commands, bridge
from spanner.share.views.self_roles import CreateSelfRolesMasterView


class SelfRolesCog(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.cogs.self_roles")

    self_roles = discord.SlashCommandGroup(
        name="self-roles",
        description="Commands for self-assignable roles"
    )

    @self_roles.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def create(self, ctx: discord.ApplicationContext):
        """Create a new self-assignable role menu"""
        view = CreateSelfRolesMasterView(ctx)
        await ctx.respond("Warning: This command is not yet finished!", view=view)
        await view.wait()


def setup(bot: bridge.Bot):
    bot.add_cog(SelfRolesCog(bot))
