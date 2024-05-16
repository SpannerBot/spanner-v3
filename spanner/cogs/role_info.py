import discord
from discord.ext import commands
from .user_info import GenericLabelledEmbedView

from spanner.share.utils import get_bool_emoji, hyperlink


class RoleInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_role_info(self, role: discord.Role) -> dict[str, discord.Embed]:
        v = role.permissions.value
        if role.permissions.administrator or v >= ((2 ** 53) - 1):
            v = 8
        perms_preview = f"https://finitereality.github.io/permissions-calculator/?v={v}"
        overview = discord.Embed(
            title=f"Role info: {role.name}",
            description=f"**ID:** `{role.id}`\n"
                        f"**Name:** {role.name}\n"
                        f"**Created:** {discord.utils.format_dt(role.created_at, 'R')}\n"
                        f"**Position:** {role.position:,}\n"
                        f"**Colour:** {(role.colour or discord.Colour.default()).value:#06x}\n"
                        f"**Mentionable:** {get_bool_emoji(role.mentionable)}\n"
                        f"**Hoisted:** {get_bool_emoji(role.hoist)}\n"
                        f"**Members:** {len(role.members):,}\n"
                        f"**Permissions:** [view online]({perms_preview})",
            colour=role.colour or discord.Colour.default(),
        )
        overview.add_field(
            name="Management",
            value=f"**Default role?** {get_bool_emoji(role.is_default())}\n"
                  f"**Booster role?** {get_bool_emoji(role.is_premium_subscriber())}\n"
                  f"**Managed by bot?** {get_bool_emoji(role.managed)}\n"
                  f"**Managed by integration?** {get_bool_emoji(role.is_integration())}",
            inline=False
        )
        result = {
            "Overview": overview
        }
        if role.icon:
            overview.set_thumbnail(url=role.icon.url)
            overview.description += f"\n**Icon URL:** {hyperlink(role.icon.url)}"
            enlarged_icon = discord.Embed(title=f"Role icon: {role.name}").set_image(url=role.icon.with_size(4096).url)
            result["Icon (large)"] = enlarged_icon

        if role.tags:
            embed = discord.Embed(
                title=f"Role tags: {role.name}",
                description="",
                colour=role.colour or discord.Colour.default()
            )
            if role.tags.bot_id:
                user = await self.bot.fetch_user(role.tags.bot_id)
                embed.description += f"**Bot:** {user.mention}\n"
            result["Tags"] = embed

        return result

    @commands.slash_command(name="role-info")
    async def role_info(self, ctx: discord.ApplicationContext, role: discord.Role):
        """Get information about a role."""
        await ctx.defer(ephemeral=True)
        embeds = await self.get_role_info(role)
        view = GenericLabelledEmbedView(ctx, **embeds)
        await ctx.respond(embed=embeds["Overview"], view=view)


def setup(bot: commands.Bot):
    bot.add_cog(RoleInfoCog(bot))
