import discord
from discord.ext import commands

from spanner.share.data import platform_emojis, public_flag_emojis
from spanner.share.utils import (
    get_bool_emoji,
    hyperlink,
)
from spanner.share.views import GenericLabelledEmbedView


class UserInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_user_info(self, user: discord.User) -> dict[str, discord.Embed]:
        user = await self.bot.fetch_user(user.id)
        lines = [
            f"**ID:** `{user.id}`",
            f"**Username:** {user.name}",
            f"**Display name:** {user.display_name}",
            f"**Discriminator:** `{user.discriminator}`" if not user.is_migrated else None,
            f"**Created:** {discord.utils.format_dt(user.created_at, 'R')}",
            f"**Accent Colour:** {user.accent_colour}",
            f"**Bot:** {get_bool_emoji(user.bot)}",
            f"**System:** {get_bool_emoji(user.system)}",
            f"**Mutual Servers** (with bot)**:** {len(user.mutual_guilds)}",
        ]
        flags = []
        for name, value in user.public_flags:
            emoji = public_flag_emojis.get(name, "") + " "
            if value:
                name = name.replace("_", " ").title()
                flags.append(f"{emoji}{name}")
        avatar_lines = [
            f"**Avatar URL:** {hyperlink(user.display_avatar.url)}",
            f"**Custom avatar URL:** {hyperlink(user.avatar.url)}" if user.avatar else None,
            f"**Default avatar URL:** {hyperlink(user.default_avatar.url)}",
            f"**Decoration URL:** {hyperlink(user.avatar_decoration.url)}" if user.avatar_decoration else None,
        ]
        overview = discord.Embed(
            title=f"{user.display_name}'s information:",
            description="\n".join(filter(None, lines)),
            colour=user.accent_colour or user.colour or discord.Colour.blurple(),
            url=user.display_avatar.url,
        )
        avatar_embed = discord.Embed(
            title=f"{user.display_name}'s avatars:",
            description="\n".join(filter(None, avatar_lines)),
            colour=user.accent_colour or user.colour or discord.Colour.blurple(),
        )
        avatar_embed.set_thumbnail(url=user.display_avatar.url)
        flags_embed = discord.Embed(
            title=f"{user.display_name}'s public flags:",
            description="\n".join(flags) or "No public flags",
            colour=user.accent_colour or user.colour or discord.Colour.blurple(),
        )
        result = {
            "Overview": overview,
            "Avatars": avatar_embed,
        }
        if flags:
            result["Public Flags"] = flags_embed
        return result

    async def get_member_info(self, member: discord.Member) -> dict[str, discord.Embed]:
        user: discord.User = await discord.utils.get_or_fetch(self.bot, "user", member.id)

        activities = []
        for current_activity in member.activities:
            activity = None
            if isinstance(current_activity, discord.Game):
                activity = "Playing %s" % current_activity.name
                if current_activity.start:
                    activity += " since %s" % discord.utils.format_dt(current_activity.start, "R")
                if current_activity.end:
                    activity += " until %s" % discord.utils.format_dt(current_activity.end, "R")
            elif isinstance(current_activity, discord.Streaming):
                activity = "[Streaming %r (%s) since %s](%s)" % (
                    current_activity.name,
                    current_activity.game,
                    discord.utils.format_dt(current_activity.created_at, "R"),
                    current_activity.url,
                )
            elif isinstance(current_activity, discord.Spotify):
                activity = "[Listening to %s by %s since %s (ends %s)](%s)" % (
                    current_activity.title,
                    " & ".join(current_activity.artists),
                    discord.utils.format_dt(current_activity.start, "R"),
                    discord.utils.format_dt(current_activity.end, "R"),
                    current_activity.track_url,
                )
            if activity:
                activities.append(activity)

        if member.desktop_status:
            platform = platform_emojis["desktop"] + " desktop"
        elif member.mobile_status:
            platform = platform_emojis["mobile"] + " mobile"
        elif member.web_status:
            platform = platform_emojis["web"] + " browser"
        else:
            platform = None
        lines = [
            f"**ID:** `{member.id}`",
            f"**Username:** {member.name}",
            f"**Display name:** {member.display_name}",
            f"**Discriminator:** `{member.discriminator}`" if not user.is_migrated else None,
            f"**Created:** {discord.utils.format_dt(member.created_at, 'R')}",
            f"**Joined:** {discord.utils.format_dt(member.joined_at, 'R')}" if member.joined_at else None,
            f"**Platform:** {platform}" if platform else None,
            f"**Passed screening:** {get_bool_emoji(not member.pending)}",
            f"**Started boosting:** {discord.utils.format_dt(member.premium_since, 'R')}"
            if member.premium_since
            else None,
            f"**Accent Colour:** {member.accent_colour}",
            f"**Bot:** {get_bool_emoji(member.bot)}",
            f"**System:** {get_bool_emoji(member.system)}",
            f"**Mutual Servers** (with bot)**:** {len(member.mutual_guilds)}",
            f"**Timed out until:** {discord.utils.format_dt(member.communication_disabled_until, 'F')}"
            if member.communication_disabled_until
            else None,
            f"**Roles:** {len(member.roles)}",
        ]

        flags = []
        for name, value in member.public_flags:
            emoji = public_flag_emojis.get(name, "") + " "
            if value:
                name = name.replace("_", " ").title()
                flags.append(f"{emoji}{name}")
        avatar_lines = [
            f"**Avatar URL:** {hyperlink(member.display_avatar.url)}",
            f"**Custom avatar URL:** {hyperlink(member.avatar.url)}" if member.avatar else None,
            f"**Default avatar URL:** {hyperlink(member.default_avatar.url)}",
            f"**Decoration URL:** {hyperlink(user.avatar_decoration.url)}" if user.avatar_decoration else None,
        ]
        overview = discord.Embed(
            title=f"{member.display_name}'s information:",
            description="\n".join(filter(None, lines)),
            colour=member.accent_colour or member.colour or discord.Colour.blurple(),
            url=member.display_avatar.url,
        )
        avatar_embed = discord.Embed(
            title=f"{member.display_name}'s avatars:",
            description="\n".join(filter(None, avatar_lines)),
            colour=member.accent_colour or member.colour or discord.Colour.blurple(),
        )
        avatar_embed.set_thumbnail(url=member.display_avatar.url)
        flags_embed = discord.Embed(
            title=f"{member.display_name}'s public flags:",
            description="\n".join(flags) or "No public flags",
            colour=member.accent_colour or member.colour or discord.Colour.blurple(),
        )

        roles = set(member.roles) - {member.guild.default_role}
        roles_text = None
        if roles:
            roles_text = ", ".join(role.mention for role in sorted(roles, reverse=True))
            if len(roles_text) > 1024:
                roles_text = ", ".join(role.mention for role in tuple(sorted(roles, reverse=True))[:10])
                roles_text += " and %d more..." % (len(roles) - 10)
        result = {
            "Overview": overview,
            "Avatars": avatar_embed,
        }
        if flags:
            result["Public Flags"] = flags_embed
        if roles:
            result["Roles"] = discord.Embed(
                title=f"{member.display_name}'s roles:",
                description=roles_text,
                colour=member.colour or discord.Colour.blurple(),
            )
        return result

    async def get_info(self, target: discord.Member | discord.User) -> dict[str, discord.Embed]:
        if isinstance(target, discord.Member):
            return await self.get_member_info(target)
        elif isinstance(target, discord.User):
            return await self.get_user_info(target)
        else:
            raise ValueError("Invalid target type")

    @commands.user_command(name="User Info")
    async def user_info(self, ctx: discord.ApplicationContext, user: discord.User | discord.Member):
        await ctx.defer(ephemeral=True)

        embeds = await self.get_info(user)
        await ctx.respond(embed=embeds["Overview"], view=GenericLabelledEmbedView(ctx, **embeds), ephemeral=True)

    @commands.slash_command(name="user-info")
    async def user_info_slash(self, ctx: discord.ApplicationContext, user: discord.User):
        """Fetches information on a user or member on discord."""
        if ctx.guild:
            try:
                user = await ctx.guild.fetch_member(user.id)
            except discord.NotFound:
                pass
        await self.user_info(ctx, user)


def setup(bot: commands.Bot):
    bot.add_cog(UserInfo(bot))
