import typing

import discord
from discord.ext import commands
from .user_info import GenericLabelledEmbedView, UserInfoCog
from spanner.share.data import verification_levels, content_filters, content_filter_names, nsfw_levels

from spanner.share.utils import get_bool_emoji


class ChannelInfoCog(commands.Cog):
    SUPPORTED_CHANNELS = [
        discord.TextChannel,
        discord.VoiceChannel,
        discord.CategoryChannel,
        discord.StageChannel,
        discord.ForumChannel,
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_channel_info(
            self,
            channel: typing.Union[*SUPPORTED_CHANNELS]
    ):
        basic_info = [
            f"**Name:** {channel.name!r}",
            f"**ID:** `{channel.id}`",
            f"**Type:** {channel.type.name}",
            f"**Created:** {discord.utils.format_dt(channel.created_at, 'R')}",
            f"**Position:** {channel.position:,}",
        ]
        return basic_info

    @commands.slash_command(name="channel-info")
    async def channel_info(self, ctx: discord.ApplicationContext, channel: discord.SlashCommandOptionType.channel = None):
        await ctx.defer(ephemeral=True)
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, tuple(self.SUPPORTED_CHANNELS)):
            return await ctx.respond("This channel type is not supported!", ephemeral=True)
        info = await self.get_channel_info(channel)
        embed = discord.Embed(
            title=f"Channel Info: {channel.name}",
            description="\n".join(info),
            colour=ctx.user.colour or discord.Colour.blurple(),
        )
        await ctx.respond(embed=embed, view=GenericLabelledEmbedView(ctx, Overview=embed), ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(ChannelInfoCog(bot))
