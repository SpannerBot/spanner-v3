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
        channel: discord.abc.GuildChannel
        basic_info = [
            f"**Name:** {channel.name!r}",
            f"**ID:** `{channel.id}`",
            f"**Category:** {channel.category.name if channel.category else 'None'}",
            f"**Permissions Synced?:** {get_bool_emoji(channel.permissions_synced)}",
            f"**Type:** {channel.type.name}",
            f"**Created:** {discord.utils.format_dt(channel.created_at, 'R')}",
            f"**Position:** {channel.position:,}",
        ]
        if channel.permissions_for(channel.guild.me).manage_channels:
            basic_info.append(f"**Invites:** {len(await channel.invites()):,}")

        results = {
            "Overview": discord.Embed(
                title=f"Channel Info: {channel.name}",
                description="\n".join(basic_info),
                colour=channel.guild.me.colour or discord.Colour.blurple(),
            )
        }

        if isinstance(channel, discord.TextChannel):
            if channel.slowmode_delay > 3600:
                slowmode = f"{channel.slowmode_delay // 3600} hours"
            elif channel.slowmode_delay > 60:
                slowmode = f"{channel.slowmode_delay // 60} minutes"
            elif channel.slowmode_delay <= 60:
                slowmode = f"{channel.slowmode_delay} seconds"
            else:
                slowmode = "Disabled"
            text_info = [
                f"**Is NSFW?** {get_bool_emoji(channel.is_nsfw())}",
                f"**Is news?** {get_bool_emoji(channel.is_news())}",
                f"**Pins:** {len(await channel.pins()):,}",
                f"**Slowmode:** {slowmode}",
                f"**Members:** {len(channel.members):,}"
            ]
            text_embed = discord.Embed(
                title=f"Text Channel Info: {channel.name}",
                description="\n".join(text_info),
                colour=channel.guild.me.colour or discord.Colour.blurple(),
            )
            if channel.topic:
                text_embed.add_field(name="Topic", value=channel.topic, inline=False)
            results["Type-specific info"] = text_embed
        return results

    @commands.slash_command(name="channel-info")
    async def channel_info(self, ctx: discord.ApplicationContext, channel: discord.SlashCommandOptionType.channel = None):
        await ctx.defer(ephemeral=True)
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, tuple(self.SUPPORTED_CHANNELS)):
            return await ctx.respond("This channel type is not supported!", ephemeral=True)
        embeds = await self.get_channel_info(channel)
        view = GenericLabelledEmbedView(ctx, **embeds)
        await ctx.respond(embed=embeds["Overview"], view=view)


def setup(bot: commands.Bot):
    bot.add_cog(ChannelInfoCog(bot))
