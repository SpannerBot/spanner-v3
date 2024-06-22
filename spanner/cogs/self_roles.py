import logging
import typing

import discord
from discord.ext import bridge, commands, pages

from spanner.share.views.self_roles import CreateSelfRolesMasterView, EditSelfRolesMasterView
from spanner.share.views import ConfirmView
from spanner.share.database import GuildConfig, SelfRoleMenu


async def self_role_menu_autocomplete(ctx: discord.ApplicationContext):
    menus = await SelfRoleMenu.filter(guild_id=ctx.guild.id).all()
    return [m.name for m in menus]


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
        await ctx.defer()
        config, _ = await GuildConfig.get_or_create(id=ctx.guild.id)
        view = CreateSelfRolesMasterView(ctx, config)
        view.update_ui()
        await ctx.respond(embed=view.embed(), view=view)
        await view.wait()
        await ctx.delete(delay=30)

    @self_roles.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def edit(
        self,
        ctx: discord.ApplicationContext,
        name: typing.Annotated[
            str,
            discord.Option(
                name="name",
                description="The name of the self-assignable role menu to delete",
                required=True,
                autocomplete=self_role_menu_autocomplete,
            ),
        ],
    ):
        """Edit a self-assignable role menu"""
        await ctx.defer()
        menu = await SelfRoleMenu.get_or_none(name=name, guild_id=ctx.guild.id)
        if not menu:
            return await ctx.respond("No self-assignable role menu with that name exists", ephemeral=True)
        await menu.fetch_related("guild")
        view = EditSelfRolesMasterView(ctx, menu)
        view.update_ui()
        await ctx.respond(embed=view.embed(), view=view)
        await view.wait()
        await ctx.delete(delay=30)

    @self_roles.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        name: typing.Annotated[
            str,
            discord.Option(
                name="name",
                description="The name of the self-assignable role menu to delete",
                required=True,
                autocomplete=self_role_menu_autocomplete,
            ),
        ],
    ):
        """Delete a self-assignable role menu"""
        await ctx.defer()
        menu = await SelfRoleMenu.get_or_none(name=name, guild_id=ctx.guild.id)
        if not menu:
            return await ctx.respond("No self-assignable role menu with that name exists", ephemeral=True)

        if not await ConfirmView(
            ctx.user, f"Are you sure you want to delete the self-assignable role menu **{menu.name}**?"
        ).ask(ctx):
            return await ctx.delete()
        await menu.delete()
        await ctx.respond(f"Deleted the self-assignable role menu **{menu.name}**", ephemeral=True)

    @self_roles.command(name="list")
    async def list_(self, ctx: discord.ApplicationContext):
        """Lists self-assignable roles in this server."""
        await ctx.defer()

        paginator = commands.Paginator("", "", 4096)
        menus = await SelfRoleMenu.filter(guild_id=ctx.guild.id).all()
        if not menus:
            return await ctx.respond("No self-assignable role menus are set up in this server", ephemeral=True)
        for menu in menus:
            channel = ctx.guild.get_channel(menu.channel)
            if not channel:
                paginator.add_line(f"* **{menu.name}** (missing channel; needs reconfiguring)")
            message = discord.utils.get(
                ctx.bot.cached_messages,
                id=menu.message,
            )
            if not message:
                try:
                    message = await channel.fetch_message(menu.message)
                except discord.NotFound:
                    paginator.add_line(f"* **{menu.name}** (missing message; needs reconfiguring)")
                    continue

            first_three = list(filter(None, map(ctx.guild.get_role, menu.roles)))[:3]
            rm = ", ".join([role.mention for role in first_three])
            if len(menu.roles) > 3:
                rm += f", *and {len(menu.roles) - 3} more*"
            paginator.add_line(f"* [**{menu.name}**]({message.jump_url}): {rm or 'no roles'}")

        embeds = [discord.Embed(description=page) for page in paginator.pages]
        pager = pages.Paginator([pages.Page(embeds=[embed]) for embed in embeds])
        await pager.respond(ctx.interaction)


def setup(bot: bridge.Bot):
    bot.add_cog(SelfRolesCog(bot))
