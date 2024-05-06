import textwrap
from typing import Annotated
from urllib.parse import urlparse

import discord
from discord import Interaction
from discord.ext import commands
from .user_info import UserInfoView, UserInfoCog
from spanner.share.data import verification_levels, content_filters, content_filter_names

from spanner.share.utils import get_bool_emoji


class ServerInfoCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def get_server_info(self, guild: discord.Guild):
        vanity_url = None
        if guild.me.guild_permissions.manage_guild:
            guild_integration_count = await guild.integrations()
            invites = await guild.invites()
            if "VANITY_URL" in guild.features:
                vanity_url = await guild.vanity_invite()
                if vanity_url:
                    vanity_url = f"[{vanity_url.code}]({vanity_url.url})"
        else:
            guild_integration_count = invites = []

        basic_info = [
            f"**Name:** {guild.name!r}",
            f"**ID:** `{guild.id}`",
            f"**Created:** {discord.utils.format_dt(guild.created_at, 'R')}",
            f"**Locale:** {guild.preferred_locale}",
            f"**Features:** {', '.join([x.replace('_', ' ').title() for x in guild.features]) or 'None'}",
        ]
        limits_info = [
            f"**Member Limit:** {guild.max_members:,} total (max {guild.max_presences:,} online)",
            f"**VC Bitrate Limit:** {round(guild.bitrate_limit / 1000)} kbps",
            f"**Max Upload Size:** {round(guild.filesize_limit / 1024 / 1024)} MB",
            f"**Max Video Channel Users:** {guild.max_video_channel_users:,}",
            f"**Max Emojis:** {guild.emoji_limit:,} ({len(guild.emojis)} used)",
            f"**Max Stickers:** {guild.sticker_limit:,} ({len(guild.stickers)} used)",
            f"**Max Roles:** 250 ({len(guild.roles)} used)",
            f"**Max Channels:** 500 ({len(guild.channels)} used)",
            f"**Max Categories:** 50 ({len(guild.categories)} used)",
            f"**Max Integrations:** 50 ({len(guild_integration_count)} used)"
            if guild.me.guild_permissions.manage_guild else
            "**Max Integrations:** 50 (missing manage server permission)",
            f"**Max Invites:** 1,000 ({len(invites)} used)" if guild.me.guild_permissions.manage_guild else
            "**Max Invites:** 1,000 (missing manage server permission)",
        ]
        invites_info = [
            f"**Invite Count:** {len(invites):,}",
            f"**Invites Paused?** {get_bool_emoji(guild.invites_disabled)}",
            f"**Vanity URL:** {vanity_url}" if vanity_url else None,
        ]
        moderation_info = [
            f"**Verification Level:** {verification_levels[guild.verification_level]}",
            f"**Content Filter:** {content_filter_names[guild.explicit_content_filter]}",
        ]

    @commands.slash_command(name="server-info")
    async def server_info(self, ctx: discord.ApplicationContext):
        pass


def setup(bot):
    bot.add_cog(ServerInfoCog(bot))
