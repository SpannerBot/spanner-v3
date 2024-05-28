import logging

import discord
from discord.ext import bridge, commands

from spanner.share.utils import get_log_channel


class JoinEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.join")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self.log.debug("%r join %r.", member, member.guild)
        if member.guild is None or member == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, member.guild.id, "member.join")
        if log_channel is None:
            return

        embed = discord.Embed(
            title="Member joined!",
            colour=discord.Colour.blue(),
            description=f"* Info: {member.mention} ({member.display_name}, `{member.id}`)\n"
            f"* Created: {discord.utils.format_dt(member.created_at, 'R')}\n"
            f"\n"
            f"* Total members: {member.guild.member_count:,}",
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_channel.send(embed=embed)


def setup(bot: bridge.Bot):
    bot.add_cog(JoinEvents(bot))
