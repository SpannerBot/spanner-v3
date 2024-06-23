import re

import discord
from discord.ext import commands


class Dehoist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.user_command(name="Dehoist")
    @discord.default_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def do_dehoist(self, ctx: discord.ApplicationContext, member: discord.Member):
        await ctx.defer(ephemeral=True)
        x = re.sub(
            r"^\W+",
            lambda _m: f"\U000017b5{member.display_name}",
            member.display_name,
        )
        if x != member.display_name:
            await member.edit(nick=x)
            await ctx.respond(f"Dehoisted {member.mention}.", ephemeral=True)
        else:
            await ctx.respond(f"{member.mention} is not hoisted.", ephemeral=True)


def setup(bot):
    bot.add_cog(Dehoist(bot))
