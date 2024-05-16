import datetime

import discord
from discord.ext import commands
from spanner.share.config import load_config


class MetaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()["cogs"]["meta"]

    @commands.slash_command(name="support")
    async def support(self, ctx: discord.ApplicationContext):
        """Get the invite link for the support server."""
        await ctx.defer(ephemeral=True)

        if invite_url := self.config.get("support_guild_invite"):
            return await ctx.respond(invite_url, ephemeral=True)

        if not self.config.get("support_guild_id"):
            owner = (await self.bot.application_info()).owner
            return await ctx.respond(
                f"This instance has not configured a support server. Try contacting the owner, {owner.mention}.",
                ephemeral=True
            )

        guild = self.bot.get_guild(self.config["support_guild_id"])
        if not guild:
            return await ctx.respond("The support server is not available.", ephemeral=True)

        invite = await guild.text_channels[0].create_invite(max_age=60 * 15, max_uses=1)
        await ctx.respond(
            "%s (expires after you use it, or %s)" % (invite.url, discord.utils.format_dt(invite.expires_at, 'R')),
            ephemeral=True
        )


def setup(bot: commands.Bot):
    bot.add_cog(MetaCog(bot))
