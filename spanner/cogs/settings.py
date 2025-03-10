import fnmatch
import typing

import discord
from discord.ext import bridge, commands
from tortoise.transactions import in_transaction

from spanner.share.config import load_config
from spanner.share.database import GuildAuditLogEntry, GuildConfig, GuildLogFeatures, GuildNickNameModeration
from spanner.share.utils import hyperlink
from spanner.share.views.confirm import ConfirmView
from spanner.share.views.settings import NicknameFilterManager


class SettingsCog(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot

    settings = discord.SlashCommandGroup(
        name="settings",
        description="Manages settings for the server.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={discord.InteractionContextType.guild},
    )

    @staticmethod
    async def _ensure_guild_config(guild_id: int):
        config, _ = await GuildConfig.get_or_create(id=guild_id)
        return config

    logging_group = discord.SlashCommandGroup(
        name="logging",
        description="Manages logging for the server.",
        default_member_permissions=discord.Permissions(manage_guild=True, manage_channels=True),
        contexts={discord.InteractionContextType.guild},
    )

    @logging_group.command(name="set-channel")
    async def set_log_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        """Sets the channels where logs will go."""
        await ctx.defer(ephemeral=True)

        if not channel.can_send(discord.Embed, discord.File):
            return await ctx.respond(
                f"\N{CROSS MARK} I need to be able to send messages, embeds, and files in {channel.mention}."
            )

        async with in_transaction() as tx:
            config = await self._ensure_guild_config(ctx.guild_id)
            old_channel_id = config.log_channel
            old_log_channel = ctx.guild.get_channel(old_channel_id) if old_channel_id else None
            config.log_channel = channel.id
            await config.save(using_db=tx)
            await GuildAuditLogEntry.generate(
                guild_id=ctx.guild.id,
                author=ctx.user,
                namespace="logging.channel",
                action="modify",
                description=f"Set the log channel to {channel.id} ({channel.name}).",
                target=channel,
                metadata={
                    "action.historical": "modified",
                    "old": {
                        "id": str(old_channel_id) if old_channel_id else None,
                        "name": old_log_channel.name if old_log_channel else None,
                    },
                    "new": {"id": str(channel.id), "name": channel.name},
                },
                using_db=tx,
            )

        await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Set the log channel to {channel.mention}.")

    log_feature = settings.create_subgroup(name="log-features", description="Manages logging features for the server.")

    async def _set_log_feature(
        self, guild_id: int, feature: str, enabled: bool = None, *, user: discord.User | discord.Member = None
    ) -> GuildLogFeatures | None:
        async with in_transaction() as tx:
            config = await self._ensure_guild_config(guild_id)
            log_feature = await GuildLogFeatures.get_or_none(guild_id=guild_id, name=feature, using_db=tx)

            if log_feature is None:
                log_feature = await GuildLogFeatures.create(guild=config, name=feature, enabled=enabled, using_db=tx)

            previous = log_feature.enabled
            log_feature.enabled = enabled if enabled is not None else not log_feature.enabled
            action = {True: "enabled", False: "disabled"}[log_feature.enabled]
            await log_feature.save()
            if user:
                await GuildAuditLogEntry.generate(
                    guild_id=guild_id,
                    author=user,
                    namespace="logging.features",
                    action=action,
                    target=log_feature,
                    description=f"set the feature `{feature}` to {'enabled' if log_feature.enabled else 'disabled'}.",
                    metadata={
                        "feature": feature,
                        "old": {
                            "enabled": previous,
                        },
                        "new": {
                            "enabled": log_feature.enabled,
                        },
                    },
                    using_db=tx,
                )
            return log_feature

    @log_feature.command(name="toggle")
    async def toggle_log_feature(
        self,
        ctx: discord.ApplicationContext,
        feature: typing.Annotated[
            str,
            discord.Option(
                name="feature",
                description="The feature to toggle.",
                required=True,
                autocomplete=discord.utils.basic_autocomplete(GuildLogFeatures.VALID_LOG_FEATURES),
            ),
        ],
    ):
        """Toggles a feature (enables if disabled, disables if enabled)."""
        await ctx.defer(ephemeral=True)
        feature = feature.lower()

        if "*" in feature:
            toggled = []
            for log_feature in GuildLogFeatures.VALID_LOG_FEATURES:
                if fnmatch.fnmatch(log_feature, feature):
                    await self._set_log_feature(ctx.guild_id, log_feature, user=ctx.user)
                    toggled.append(log_feature)
            return await ctx.respond(
                f"\N{WHITE HEAVY CHECK MARK} Toggled the following features: {', '.join(toggled)}."
            )

        if feature not in GuildLogFeatures.VALID_LOG_FEATURES:
            return await ctx.respond(f"\N{CROSS MARK} The feature `{feature}` does not exist.")

        log_feature = await self._set_log_feature(ctx.guild_id, feature, user=ctx.user)

        await ctx.respond(
            f"\N{WHITE HEAVY CHECK MARK} {'Enabled' if log_feature.enabled else 'Disabled'} the feature `{feature}`."
        )

    @log_feature.command(name="enable")
    async def enable_log_feature(
        self,
        ctx: discord.ApplicationContext,
        feature: typing.Annotated[
            str,
            discord.Option(
                name="feature",
                description="The feature to enable.",
                required=True,
                autocomplete=discord.utils.basic_autocomplete(GuildLogFeatures.VALID_LOG_FEATURES),
            ),
        ],
    ):
        """Enables a feature."""
        await ctx.defer(ephemeral=True)
        feature = feature.lower()
        if "*" in feature:
            toggled = []
            for log_feature in GuildLogFeatures.VALID_LOG_FEATURES:
                if fnmatch.fnmatch(log_feature, feature):
                    await self._set_log_feature(ctx.guild_id, log_feature, True, user=ctx.user)
                    toggled.append(log_feature)
            return await ctx.respond(
                f"\N{WHITE HEAVY CHECK MARK} Enabled the following features: {', '.join(toggled)}."
            )

        if feature not in GuildLogFeatures.VALID_LOG_FEATURES:
            return await ctx.respond(f"\N{CROSS MARK} The feature `{feature}` does not exist.")

        await self._set_log_feature(ctx.guild_id, feature, True, user=ctx.user)
        await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Enabled the feature `{feature}`.")

    @log_feature.command(name="disable")
    async def disable_log_feature(
        self,
        ctx: discord.ApplicationContext,
        feature: typing.Annotated[
            str,
            discord.Option(
                name="feature",
                description="The feature to enable.",
                required=True,
                autocomplete=discord.utils.basic_autocomplete(GuildLogFeatures.VALID_LOG_FEATURES),
            ),
        ],
    ):
        """Disables a feature."""
        await ctx.defer(ephemeral=True)
        feature = feature.lower()
        if "*" in feature:
            toggled = []
            for log_feature in GuildLogFeatures.VALID_LOG_FEATURES:
                if fnmatch.fnmatch(log_feature, feature):
                    await self._set_log_feature(ctx.guild_id, log_feature, False, user=ctx.user)
                    toggled.append(log_feature)
            return await ctx.respond(
                f"\N{WHITE HEAVY CHECK MARK} Disabled the following features: {', '.join(toggled)}."
            )

        if feature not in GuildLogFeatures.VALID_LOG_FEATURES:
            return await ctx.respond(f"\N{CROSS MARK} The feature `{feature}` does not exist.")

        await self._set_log_feature(ctx.guild_id, feature, False, user=ctx.user)
        await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Disabled the feature `{feature}`.")

    @settings.command(name="nickname-filtering")
    async def manage_nickname_filtering(
        self,
        ctx: discord.ApplicationContext,
    ):
        """Enables AI-based nickname filtering."""
        await ctx.defer(ephemeral=True)

        exists = await GuildNickNameModeration.get_or_none(guild_id=ctx.guild_id)
        if not exists:
            if not await ConfirmView(
                ctx.user,
                "Nickname filtering utilises "
                "[OpenAI's moderation](https://platform.openai.com/docs/guides/moderation/overview) services. "
                "Whenever a member joins, or updates their nickname, their display name is sent to OpenAI for "
                "analysis. You should put a prominent notice in your server rules or guidelines to inform your "
                "members that their display names are being sent to OpenAI for analysis, for privacy reasons. "
                "\n"
                "Do you consent to enabling AI-based nickname filtering?",
            ).ask(ctx):
                return await ctx.edit(content="Cancelled.", embed=None, view=None)

        config = await self._ensure_guild_config(ctx.guild_id)
        v = NicknameFilterManager(config)
        await ctx.respond(view=v)


def setup(bot):
    bot.add_cog(SettingsCog(bot))
