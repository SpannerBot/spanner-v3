from typing import Annotated

import discord
from discord.ext import commands

from spanner.share.utils import get_bool_emoji, hyperlink
from spanner.share.views import GenericLabelledEmbedView


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

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
            values_user.append(f"**Avatar URL**: {hyperlink(user.avatar.url)}")
        else:
            values_user.append(f"**Default Avatar URL**: {hyperlink(user.default_avatar.url)}")
        if user.banner is not None:
            values_user.append(f"**Banner URL**: {hyperlink(user.banner.url)}")
        if user.avatar_decoration is not None:
            values_user.append(f"**Avatar Decoration URL**: {hyperlink(user.avatar_decoration.url)}")

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
            values_user.append(f"**Bot Invite**: {hyperlink(link)}")

        values_member = []

        if isinstance(user, discord.Member):
            values_member = [
                f"**Joined:** {discord.utils.format_dt(user.joined_at or discord.utils.utcnow(), 'R')}",
                f"**Nickname:** {discord.utils.escape_markdown(user.nick)}" if user.nick else None,
                f"**Passed Onboarding:** {get_bool_emoji(not user.pending)}",
                f"**Top Role:** {user.top_role.mention}",
            ]
            if user.display_avatar != user.avatar:
                values_member.append("**Display Avatar**: %s" % hyperlink(user.display_avatar.url))

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

        view = GenericLabelledEmbedView(ctx, **embeds)
        await ctx.respond(embed=embed, view=view)

    @commands.user_command(name="User Info")
    async def cmd_user_info(self, ctx: discord.ApplicationContext, member: discord.Member):
        cmd: discord.ApplicationCommand = self.bot.get_application_command("user-info")
        # noinspection PyTypeChecker
        await ctx.invoke(cmd, user=member)


def setup(bot):
    bot.add_cog(UserInfoCog(bot))
