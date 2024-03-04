from ..data import *
from ..utils import get_bool_emoji
from typing import Annotated
import textwrap
import discord
from discord.ext import commands
from urllib.parse import urlparse


class UserInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def first_line(text: str, max_length: int = 100, placeholder: str = "...") -> str:
        line = text.splitlines(False)[0]
        return textwrap.shorten(line, max_length, placeholder=placeholder)

    @staticmethod
    def hyperlink(url: str, text: str = ...):
        if text is ...:
            parsed = urlparse(url)
            text = parsed.hostname.lower()

        return f"[{text}]({url})"

    def get_user_data(self, user: discord.User | discord.Member) -> tuple[list[str], list[str]]:
        # noinspection PyUnresolvedReferences
        values_user = [
            f"**ID**: `{user.id}`",
            f"**Username**: {discord.utils.escape_markdown(user.name)}",
            f"**Discriminator/tag**: `#{user.discriminator}`" if not user.is_migrated else None,
            f"**Status**: {user.status.name.title()}" if hasattr(user, "status") else None,
            f"**Created**: <t:{round(user.created_at.timestamp())}:R>",
            f"**Is a bot?** {get_bool_emoji(user.bot)}",
            f"**Is a system user?** {get_bool_emoji(user.system)}",
        ]

        if user.avatar is not None:
            values_user.append(f"**Avatar URL**: {self.hyperlink(user.avatar.url)}")
        else:
            values_user.append(f"**Default Avatar URL**: {self.hyperlink(user.default_avatar.url)}")
        if user.banner is not None:
            values_user.append(f"**Banner URL**: {self.hyperlink(user.banner.url)}")

        if user.bot is True:
            link = discord.utils.oauth_url(
                user.id,
                scopes=("bot",),
            )
            values_user.append(f"**Bot Invite**: {self.hyperlink(link)}")

        values_member = []

        if isinstance(user, discord.Member):
            values_member = [
                f"**Joined:** {discord.utils.format_dt(user.joined_at or discord.utils.utcnow(), 'R')}",
                f"**Nickname:** {discord.utils.escape_markdown(user.nick)}" if user.nick else None
            ]
            if user.display_avatar != user.avatar:
                values_member.append("**Display Avatar**: %s" % self.hyperlink(user.display_avatar.url))

            if user.communication_disabled_until and user.communication_disabled_until >= discord.utils.utcnow():
                values_member.append(
                    f"**Timeout expires:** <t:{round(user.communication_disabled_until.timestamp())}:R>"
                )

            if user.premium_since:
                values_member.append(
                    f"**Started boosting:** {discord.utils.format_dt(user.premium_since, 'R')}"
                )

        return list(filter(None, values_user)), list(filter(None, values_member))

    @commands.slash_command(name="user-info")
    async def user_info(
            self,
            ctx: discord.ApplicationContext,
            user: Annotated[
                discord.User,
                discord.Option(
                    discord.User,
                    name="user",
                    description="The user name/id/mention to get info about. Defaults to yourself.",
                    required=False,
                    default=None
                )
            ] = None
    ):
        """Fetches information about a given user or member."""
        user = user or ctx.user
        await ctx.defer(ephemeral=True)
        user = await discord.utils.get_or_fetch(ctx.guild, "member", user.id, default=user)
        user_data, member_data = self.get_user_data(user)

