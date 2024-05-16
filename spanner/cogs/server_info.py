import discord
from discord.ext import commands
from .user_info import GenericLabelledEmbedView
from spanner.share.data import verification_levels, content_filters, content_filter_names, nsfw_levels

from spanner.share.utils import get_bool_emoji, hyperlink


class ServerInfoCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def get_server_info(self, guild: discord.Guild):
        vanity_url = None
        if guild.me.guild_permissions.manage_guild:
            auto_mod_rules = await guild.fetch_auto_moderation_rules()
            guild_integration_count = await guild.integrations()
            invites = await guild.invites()
            if "VANITY_URL" in guild.features:
                vanity_url = await guild.vanity_invite()
                if vanity_url:
                    vanity_url = f"[{vanity_url.code}]({vanity_url.url})"
        else:
            guild_integration_count = invites = auto_mod_rules = []

        if guild.me.guild_permissions.ban_members:
            bans = await guild.bans().flatten()
            ban_count = len(bans)
        else:
            ban_count = None

        basic_info = [
            f"**Name:** {guild.name!r}",
            f"**ID:** `{guild.id}`",
            f"**Created:** {discord.utils.format_dt(guild.created_at, 'R')}",
            f"**Locale:** {guild.preferred_locale}",
            f"**Features:** {', '.join([x.replace('_', ' ').title() for x in guild.features]) or 'None'}",
        ]
        if guild.icon:
            basic_info.append(f"**Icon URL:** {hyperlink(guild.icon.url)}")
        if guild.banner:
            basic_info.append(f"**Banner URL:** {hyperlink(guild.banner.url)}")
        inf = float('inf')
        limits_info = [
            f"**Member Limit:** {guild.max_members or inf:,} total (max {guild.max_presences or inf:,} online)",
            f"**VC Bitrate Limit:** {round(guild.bitrate_limit / 1000)} kbps",
            f"**Max Upload Size:** {round(guild.filesize_limit / 1024 / 1024)} MB",
            f"**Max Video Channel Users:** {guild.max_video_channel_users or inf:,}",
            f"**Max Emojis:** {guild.emoji_limit:,} ({len(guild.emojis)} used)",
            f"**Max Stickers:** {guild.sticker_limit:,} ({len(guild.stickers)} used)",
            f"**Max Roles:** 250 ({len(guild.roles)} used)",
            f"**Max Channels:** 500 ({len(guild.channels)} used)",
            f"**Max Categories:** 50 ({len(guild.categories)} used)",
            f"**Max Integrations:** 50 ({len(guild_integration_count)} used)"
            if guild.me.guild_permissions.manage_guild else
            "**Max Integrations:** 50 (*missing manage server permission*)",
            f"**Max Invites:** 1,000 ({len(invites)} used)" if guild.me.guild_permissions.manage_guild else
            "**Max Invites:** 1,000 (*missing manage server permission*)",
            f"**Max Auto Mod Rules:** 10 ({len(auto_mod_rules)} used)" if guild.me.guild_permissions.manage_guild else
            "**Max Auto Mod Rules:** 10 (*missing manage server permission*)",
        ]
        invites_info = [
            f"**Invite Count:** {len(invites):,}",
            f"**Invites Paused?** {get_bool_emoji(guild.invites_disabled)}",
            f"**Vanity URL:** {vanity_url}" if vanity_url else None,
        ]
        moderation_info = [
            f"**Verification Level:** {verification_levels[guild.verification_level]}",
            f"**Content Filter:** {content_filter_names[guild.explicit_content_filter]} "
            f"({content_filters[guild.explicit_content_filter]})",
            f"**NSFW Level:** {nsfw_levels[guild.nsfw_level]}",
            f"**Requires 2FA for moderation actions?** {get_bool_emoji(guild.mfa_level)}",
            f"**System Channel:** {guild.system_channel or 'None'}",
            f"**Rules Channel:** {guild.rules_channel or 'None'}",
            f"**Auto Mod Rules:** {len(auto_mod_rules):,} ({', '.join([repr(x.name) for x in auto_mod_rules])})"
            if guild.me.guild_permissions.manage_guild else '**Auto Mod Rules:** *missing manage server permission*',
            f"**Bans:** {ban_count:,}" + "+" if ban_count and ban_count >= 1000 else "",
        ]
        if guild_integration_count:
            integrations = []
            for integration in guild_integration_count:
                it = integration.type.title()
                if it == "Discord":
                    it = "Discord App"
                ln = f"**{it}:** {integration.name or 'Unnamed'}"
                extra_info = []
                if integration.account:
                    _user = guild.get_member(int(integration.account.id))
                    if _user:
                        url = discord.utils.oauth_url(
                            _user.id, scopes=["bot"]
                        )
                        extra_info.append(f"[Bot: {_user.name}]({url})")
                if integration.user:
                    extra_info.append(f"Added by: {integration.user.mention}")
                if extra_info:
                    ln += f" ({', '.join(extra_info)})"
                integrations.append(ln)
        else:
            integrations = []
        return {
            "overview_info": basic_info,
            "limits_info": limits_info,
            "invites_info": invites_info,
            "moderation_info": moderation_info,
            "integrations_info": integrations,
        }

    @commands.slash_command(name="server-info")
    async def server_info(self, ctx: discord.ApplicationContext):
        """Get information about the server."""
        await ctx.defer(ephemeral=True)
        data = await self.get_server_info(ctx.guild)

        embeds = {}
        for key, value in data.items():
            value = [x for x in value if x]
            if not value:
                continue
            embed = discord.Embed(title=key.replace("_", " ").title(), color=discord.Color.blurple())
            embed.description = "\n".join(value)
            embeds[key.split("_")[0].title()] = embed

        if ctx.guild.icon:
            embeds["Overview"].set_thumbnail(url=ctx.guild.icon.url)
            embeds["Icon (Enlarged)"] = discord.Embed().set_image(url=ctx.guild.icon.with_size(4096).url)
        if ctx.guild.banner:
            embeds["Overview"].set_image(url=ctx.guild.banner.url)
        await ctx.respond(embed=embeds["Overview"], view=GenericLabelledEmbedView(ctx, **embeds))


def setup(bot):
    bot.add_cog(ServerInfoCog(bot))
