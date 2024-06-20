import logging

import discord
from discord.ext import bridge, commands

from spanner.share.views.self_roles import CreateSelfRolesMasterView
from spanner.share.database import GuildConfig


class SelfRolesCog(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.cogs.self_roles")

    self_roles = discord.SlashCommandGroup(name="self-roles", description="Commands for self-assignable roles")

    @self_roles.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def create(self, ctx: discord.ApplicationContext):
        """Create a new self-assignable role menu"""
        config, _ = await GuildConfig.get_or_create(id=ctx.guild.id)
        view = CreateSelfRolesMasterView(ctx, config)
        view.update_ui()
        await ctx.respond(":warning: This command is not yet finished!", embed=view.embed(), view=view)
        await view.wait()
        await ctx.delete(delay=30)


def setup(bot: bridge.Bot):
    bot.add_cog(SelfRolesCog(bot))
