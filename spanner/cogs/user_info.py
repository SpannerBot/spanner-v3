import textwrap
from typing import Annotated
from urllib.parse import urlparse

import discord
from discord import Interaction
from discord.ext import commands

from spanner.share.utils import get_bool_emoji


class UserInfoView(discord.ui.View):
    class EmbedSwitchButton(discord.ui.Button):
        def __init__(self, embed_name: str, embed: discord.Embed):
            super().__init__(
                label=embed_name,
                custom_id=embed_name,
            )
            self.embed = embed

        def update_view(self):
            for child in self.view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = False
                    child.style = discord.ButtonStyle.secondary
                    if child == self:
                        child.disabled = True
                        child.style = discord.ButtonStyle.primary

        async def callback(self, interaction: discord.Interaction):
            self.update_view()
            await interaction.response.edit_message(embed=self.embed, view=self.view)

    def __init__(self, ctx: discord.ApplicationContext, **embeds: discord.Embed):
        super().__init__(timeout=900, disable_on_timeout=True)  # 15 minutes, the length of an ephemeral message
        self.embeds = embeds
        self.ctx = ctx

        for embed_key, embed_value in self.embeds.items():
            self.add_item(self.EmbedSwitchButton(embed_key, embed_value))
        # noinspection PyUnresolvedReferences
        self.children[0].update_view()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.ctx.user.id


class UserInfoCog(commands.Cog):
    MODERATION_PERMISSIONS = {
        "manage_members",
        "manage_roles",
        "manage_channels",
        "manage_expressions",
        "manage_messages",
        "manage_webhooks",
        "manage_emojis",
        "kick_members",
        "ban_members",
        "mute_members",
        "deafen_members",
        "move_members",
        "manage_nicknames",
        "moderate_members",
        "view_audit_log",
        "manage_threads",
        "administrator",
    }

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def first_line(text: str, max_length: int = 100, placeholder: str = "...") -> str:
        line = text.splitlines()[0]
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
            f"**Created**: {discord.utils.format_dt(user.created_at, 'R')}",
            f"**Is a bot?** {get_bool_emoji(user.bot)}",
            f"**Is a system user?** {get_bool_emoji(user.system)}",
            (
                f"**Accent Colour**: {user.accent_colour:0>6x}"
                if user.accent_colour
                else None if not user.is_migrated else None
            ),
        ]

        if user.avatar is not None:
            values_user.append(f"**Avatar URL**: {self.hyperlink(user.avatar.url)}")
        else:
            values_user.append(f"**Default Avatar URL**: {self.hyperlink(user.default_avatar.url)}")
        if user.banner is not None:
            values_user.append(f"**Banner URL**: {self.hyperlink(user.banner.url)}")
        if user.avatar_decoration is not None:
            values_user.append(f"**Avatar Decoration URL**: {self.hyperlink(user.avatar_decoration.url)}")

        puf = []
        for flag, value in user.public_flags:
            if value:
                puf.append(flag.replace("_", " ").title())
        if puf:
            values_user.append(f"**Public User Flags**: {', '.join(puf)}")

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
                f"**Nickname:** {discord.utils.escape_markdown(user.nick)}" if user.nick else None,
                f"**Passed Onboarding:** {get_bool_emoji(not user.pending)}",
                f"**Top Role:** {user.top_role.mention}",
            ]
            if user.display_avatar != user.avatar:
                values_member.append("**Display Avatar**: %s" % self.hyperlink(user.display_avatar.url))

            if user.communication_disabled_until and user.communication_disabled_until >= discord.utils.utcnow():
                values_member.append(
                    f"**Timeout expires:** <t:{round(user.communication_disabled_until.timestamp())}:R>"
                )

            if user.premium_since:
                values_member.append(f"**Started boosting:** {discord.utils.format_dt(user.premium_since, 'R')}")

            mod_perms = []
            for permission_name, granted in user.guild_permissions:
                if granted and permission_name in self.MODERATION_PERMISSIONS:
                    mod_perms.append(permission_name.replace("_", " ").title())
            if mod_perms:
                values_member.insert(0, "**Moderation Permissions:** " + ", ".join(mod_perms))

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
                default=None,
            ),
        ] = None,
    ):
        """Fetches information about a given user or member."""
        user = user or ctx.user
        await ctx.defer(ephemeral=True)
        user: discord.User | discord.Member = await discord.utils.get_or_fetch(
            ctx.guild, "member", user.id, default=user
        )
        user_data, member_data = self.get_user_data(user)
        embed = discord.Embed(
            title=f"User info for {user}",
            description="\n".join(user_data),
            colour=user.colour or discord.Colour.blurple(),
        )
        embeds = {"Overview": embed}
        if member_data:
            embed.add_field(name="Server-specific information", value="\n".join(member_data), inline=False)

        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
            avatar_embed = discord.Embed(title=f"Avatar for {user}", colour=user.colour or discord.Colour.blurple())
            avatar_embed.set_image(url=user.display_avatar.with_size(4096).url)
            embeds["Avatar (Large)"] = avatar_embed

        if user.banner:
            embed.set_image(url=user.banner.url)

        if member_data:
            block = "\n".join(reversed([role.mention for role in user.roles]))
            roles_embed = discord.Embed(
                title=f"Roles for {user}", description=block[:4096], colour=user.colour or discord.Colour.blurple()
            )
            embeds["Roles"] = roles_embed

            if user.guild_permissions.administrator is False:
                permissions_embed = discord.Embed(
                    title=f"Guild-wide permissions for {user}",
                    description="\n".join([x.replace("_", " ").title() for x, y in user.guild_permissions if y]),
                    colour=user.colour or discord.Colour.blurple(),
                )
                embeds["Permissions"] = permissions_embed

                channel_permissions = discord.Embed(
                    title=f"Channel permissions for {user}",
                    description="\n".join(
                        [x.replace("_", " ").title() for x, y in ctx.channel.permissions_for(user) if y]
                    ),
                    colour=user.colour or discord.Colour.blurple(),
                )
                if user.guild_permissions != ctx.channel.permissions_for(user):
                    embeds["Channel Permissions"] = channel_permissions
            else:
                embeds["Permissions"] = discord.Embed(
                    title="Permissions",
                    description="This user has the `Administrator` permission, which grants all permissions.",
                    colour=user.colour or discord.Colour.blurple(),
                )

        view = UserInfoView(ctx, **embeds)
        await ctx.respond(embed=embed, view=view)


def setup(bot):
    bot.add_cog(UserInfoCog(bot))
