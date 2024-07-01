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

        cog = self.bot.get_cog("UserInfo")
        # noinspection PyUnresolvedReferences
        user_info_embed = (await cog.get_member_info(member))["Overview"]
        embed = discord.Embed(
            title="Member joined!",
            colour=discord.Colour.blue(),
            description=f"There are now {member.guild.member_count:,} members in this server.",
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_channel.send(embeds=[embed, user_info_embed])


def setup(bot: bridge.Bot):
    bot.add_cog(JoinEvents(bot))
