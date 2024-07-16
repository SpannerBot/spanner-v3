import typing

import discord
from discord.ext import commands

from spanner.share.utils import get_bool_emoji
from spanner.share.views import GenericLabelledEmbedView


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

    async def get_channel_info(self, channel: typing.Union[*SUPPORTED_CHANNELS]):
        def humanise(v: int, *, precise: bool = False):
            def pluralise(word: str, value: int | float):
                value = round(value)
                if value == 1:
                    return f"{value:,} {word}"
                return f"{value:,} {word}s"

            if precise:
                _end = []
                minutes, seconds = divmod(v, 60)
                hours, minutes = divmod(minutes, 60)
                days, hours = divmod(hours, 24)
                if days:
                    _end.append(pluralise("day", days))
                if hours:
                    _end.append(pluralise("hour", hours))
                if minutes:
                    _end.append(pluralise("minute", minutes))
                if seconds:
                    _end.append(pluralise("second", seconds))
                return ", ".join(_end)
            else:
                if v >= 86400:
                    return pluralise("day", v / 86400)
                elif v >= 3600:
                    return pluralise("hour", v / 3600)
                elif v >= 60:
                    return pluralise("minute", v / 60)
                return pluralise("second", v)

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
        if channel.guild.me and channel.permissions_for(channel.guild.me).manage_channels:
            try:
                basic_info.append(f"**Invites:** {len(await channel.invites()):,}")
            except discord.HTTPException:
                pass

        results = {
            "Overview": discord.Embed(
                title=f"Channel Info: {channel.name}",
                description="\n".join(basic_info),
                colour=discord.Colour.blurple(),
            )
        }

        if isinstance(channel, discord.TextChannel):
            if (channel.slowmode_delay or 0) > 0:
                slowmode = humanise(channel.slowmode_delay)
            else:
                slowmode = "Disabled"
            try:
                pins = f"{len(await channel.pins()):,}"
            except discord.HTTPException:
                pins = "?"
            text_info = [
                f"**Is NSFW?** {get_bool_emoji(channel.is_nsfw())}",
                f"**Is news?** {get_bool_emoji(channel.is_news())}",
                f"**Pins:** {pins}",
                f"**Slowmode:** {slowmode}",
                f"**Members:** {len(channel.members):,}",
            ]
            text_embed = discord.Embed(
                title=f"Text Channel Info: {channel.name}",
                description="\n".join(text_info),
                colour=discord.Colour.blurple(),
            )
            if channel.topic:
                text_embed.add_field(name="Topic", value=channel.topic, inline=False)
            results["Text-specific info"] = text_embed
        elif isinstance(channel, discord.ForumChannel):
            if (channel.slowmode_delay or 0) > 0:
                slowmode = humanise(channel.slowmode_delay)
            else:
                slowmode = "Disabled"

            if (channel.default_thread_slowmode_delay or 0) > 0:
                thread_slowmode = humanise(channel.default_thread_slowmode_delay)
            else:
                thread_slowmode = "Disabled"

            auto_duration = humanise(channel.default_auto_archive_duration * 60)
            order = channel.default_sort_order.name if channel.default_sort_order else "Recent Activity"
            order = order.replace("_", " ").title()
            forum_info = [
                f"**Is NSFW?** {get_bool_emoji(channel.is_nsfw())}",
                f"**Members:** {len(channel.members):,}",
                f"**Slowmode:** {slowmode}",
                f"**Default auto archive duration:** {auto_duration}",
                f"**Default reaction emoji:** {getattr(channel, 'default_reaction_emoji', None)}",
                f"**Default sort order:** {order}",
                f"**Default thread slowmode:** {thread_slowmode}",
                f"**Posts require tags:** {get_bool_emoji(channel.requires_tag)}",
            ]
            forum_embed = discord.Embed(
                title=f"Forum Channel Info: {channel.name}",
                description="\n".join(forum_info),
                colour=discord.Colour.blurple(),
            )
            if channel.topic:
                forum_embed.add_field(name="Guidelines", value=channel.topic, inline=False)
            results["Forum-specific info"] = forum_embed

            tags_embed = discord.Embed(
                title=f"Available tags for {channel.name}:",
                colour=discord.Colour.blurple(),
            )
            for tag in channel.available_tags:
                tags_embed.add_field(
                    name=tag.name,
                    value=f"**ID:** `{tag.id}`\n"
                    f"**Moderator Only?** {get_bool_emoji(tag.moderated)}\n"
                    f"**Emoji:** {tag.emoji if tag.emoji.name != '_' else None!s}\n",
                )
            if tags_embed.fields:
                results["Available tags"] = tags_embed
        elif isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            if channel.video_quality_mode == discord.VideoQualityMode.auto:
                video_quality = "Automatic"
            else:
                video_quality = "720p"
            voice_info = [
                f"**Bitrate:** {round(channel.bitrate / 1000)}kbps",
                f"**Members:** {len(channel.members):,}",
                f"**User limit:** {channel.user_limit:,}",
                f"**Region:** {channel.rtc_region.value if channel.rtc_region else 'Automatic'}",
                f"**Video quality:** {video_quality}",
            ]
            voice_embed = discord.Embed(
                title=f"Voice Channel Info: {channel.name}",
                description="\n".join(voice_info),
                colour=discord.Colour.blurple(),
            )
            results["Voice-specific info"] = voice_embed

            if isinstance(channel, discord.StageChannel):
                stage_info = [
                    f"**Listeners:** {len(channel.listeners):,}",
                    f"**Speakers:** {len(channel.speakers):,}",
                    f"**Moderators:** {len(channel.moderators):,}",
                    f"**Requesting to speak:** {len(channel.requesting_to_speak):,}",
                    f"**User limit:** {channel.user_limit or 'None'}",
                ]
                stage_embed = discord.Embed(
                    title=f"Stage Channel Info: {channel.name}",
                    description="\n".join(stage_info),
                    colour=discord.Colour.blurple(),
                )
                results["Stage-specific info"] = stage_embed
                if channel.instance:
                    event_info = [
                        f"**Stage privacy level:** {channel.instance.privacy_level.name}",
                        f"**Discoverability enabled?** {get_bool_emoji(not channel.instance.discoverable_disabled)}",
                    ]
                    event_embed = discord.Embed(
                        title=f"Stage Instance Info: {channel.name}",
                        description="\n".join(event_info),
                        colour=discord.Colour.blurple(),
                    )
                    if channel.instance.scheduled_event:
                        start = discord.utils.format_dt(channel.instance.scheduled_event.start_time, "R")
                        end = discord.utils.format_dt(channel.instance.scheduled_event.end_time, "R")
                        duration = humanise(
                            (
                                channel.instance.scheduled_event.end_time - channel.instance.scheduled_event.start_time
                            ).total_seconds(),
                            precise=True,
                        )
                        subscribers = channel.instance.scheduled_event.subscriber_count
                        creator = channel.instance.scheduled_event.creator
                        if not creator:
                            creator = await self.bot.fetch_user(channel.instance.scheduled_event.creator_id)
                        event_embed.add_field(
                            name="Scheduled Event",
                            value=f"**Starts:** {start}\n"
                            f"**Ends:** {end} (total duration: {duration})\n"
                            f"**Creator:** {creator.mention}\n"
                            f"**Name:** {channel.instance.scheduled_event.name!r}\n"
                            f"**Interested:** {subscribers:,}",
                        )
                    results["Event-specific info"] = event_embed
        elif isinstance(channel, discord.CategoryChannel):
            category_info = [
                f"**Channels:** {len(channel.channels):,}",
                f"**Text Channels:** {len(channel.text_channels):,}",
                f"**Forum Channels** {len(channel.forum_channels):,}",
                f"**Voice Channels:** {len(channel.voice_channels):,}",
                f"**Stage Channels:** {len(channel.stage_channels):,}",
            ]
            category_embed = discord.Embed(
                title=f"Category Channel Info: {channel.name}",
                description="\n".join(category_info),
                colour=discord.Colour.blurple(),
            )
            results["Category-specific info"] = category_embed
        return results

    @commands.slash_command(
        name="channel-info",
        integration_types={discord.IntegrationType.guild_install, discord.IntegrationType.user_install},
    )
    async def channel_info(
        self, ctx: discord.ApplicationContext, channel: discord.SlashCommandOptionType.channel = None
    ):
        """Displays information about a channel."""
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
