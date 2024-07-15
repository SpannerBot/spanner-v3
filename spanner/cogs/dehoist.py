import re

import discord
from discord.ext import commands


CHAR = "\U000017b5"


class Dehoist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.user_command(name="Dehoist", context={discord.InteractionContextType.guild})
    @discord.default_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def do_dehoist(self, ctx: discord.ApplicationContext, member: discord.Member):
        await ctx.defer(ephemeral=True)
        if member.display_name.startswith(CHAR):
            await ctx.respond(f"{member.mention} is already de-hoisted.", ephemeral=True)
        else:
            x = f"{CHAR}{member.display_name}"[:32]
            await member.edit(nick=x, reason=f"Dehoisted by @{ctx.user.global_name}")
            await ctx.respond(f"Dehoisted {member.mention}.", ephemeral=True)


def setup(bot):
    bot.add_cog(Dehoist(bot))
