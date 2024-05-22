import typing

import discord
from discord.ext import bridge, commands

from spanner.share.database import GuildAuditLogEntry, GuildConfig, GuildLogFeatures


class SettingsCog(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot

    settings = discord.SlashCommandGroup(
        name="settings",
        description="Manages settings for the server.",
        default_member_permissions=discord.Permissions(manage_guild=True)
    )

    @staticmethod
    async def _ensure_guild_config(guild_id: int):
        config = await GuildConfig.get_or_none(id=guild_id)

        if config is None:
            config = await GuildConfig.create(id=guild_id)

        return config

    @settings.command(name="set-log-channel")
    async def set_log_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        """Sets the channels where logs will go."""
        await ctx.defer(ephemeral=True)

        if not channel.can_send(discord.Embed, discord.File):
            return await ctx.respond(
                f"\N{cross mark} I need to be able to send messages, embeds, and files in {channel.mention}."
            )

        config = await self._ensure_guild_config(ctx.guild_id)
        config.log_channel = channel.id
        await config.save()
        await GuildAuditLogEntry.create(
            guild=config,
            author=ctx.user.id,
            namespace="settings.logging.channels.main",
            action="set",
            description=f"Set the log channel to {channel.id} ({channel.name})."
        )

        await ctx.respond(f"\N{white heavy check mark} Set the log channel to {channel.mention}.")

    log_feature = settings.create_subgroup(
        name="log-features",
        description="Manages logging features for the server."
    )

    async def _set_log_feature(
            self,
            guild_id: int,
            feature: str,
            enabled: bool = None,
            *,
            user_id: int = None
    ) -> GuildLogFeatures | None:
        config = await self._ensure_guild_config(guild_id)
        log_feature = await GuildLogFeatures.get_or_none(
            guild_id=guild_id,
            name=feature
        )

        if log_feature is None:
            log_feature = await GuildLogFeatures.create(
                guild=config,
                name=feature,
                enabled=enabled
            )

        log_feature.enabled = enabled if enabled is not None else not log_feature.enabled
        await log_feature.save()
        if user_id:
            await GuildAuditLogEntry.create(
                guild=config,
                author=user_id,
                namespace=f"settings.logging.features.{feature}",
                action="toggle",
                description=f"Toggled the feature `{feature}` to {'enabled' if log_feature.enabled else 'disabled'}."
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
                    autocomplete=discord.utils.basic_autocomplete(GuildLogFeatures._VALID_LOG_FEATURES)
                )
            ]
    ):
        """Toggles a feature (enables if disabled, disables if enabled)."""
        await ctx.defer(ephemeral=True)
        feature = feature.lower()
        if feature not in GuildLogFeatures._VALID_LOG_FEATURES:
            return await ctx.respond(f"\N{cross mark} The feature `{feature}` does not exist.")

        config = await self._ensure_guild_config(ctx.guild_id)
        log_feature = await GuildLogFeatures.get_or_none(
            guild_id=ctx.guild_id,
            name=feature
        )

        if log_feature is None:
            log_feature = await GuildLogFeatures.create(
                guild=config,
                name=feature,
                enabled=False
            )

        log_feature.enabled = not log_feature.enabled
        await log_feature.save()
        await GuildAuditLogEntry.create(
            guild=config,
            author=ctx.user.id,
            namespace=f"settings.logging.features.{feature}",
            action="toggle",
            description=f"Toggled the feature `{feature}` to {'enabled' if log_feature.enabled else 'disabled'}."
        )

        await ctx.respond(
            f"\N{white heavy check mark} {'Enabled' if log_feature.enabled else 'Disabled'} the feature `{feature}`."
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
                    autocomplete=discord.utils.basic_autocomplete(GuildLogFeatures._VALID_LOG_FEATURES)
                )
            ]
    ):
        """Enables a feature."""        
        await ctx.defer(ephemeral=True)
        feature = feature.lower()
        if feature not in GuildLogFeatures._VALID_LOG_FEATURES:
            return await ctx.respond(f"\N{cross mark} The feature `{feature}` does not exist.")

        await self._set_log_feature(ctx.guild_id, feature, True, user_id=ctx.user.id)
        await ctx.respond(
            f"\N{white heavy check mark} Enabled the feature `{feature}`."
        )

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
                    autocomplete=discord.utils.basic_autocomplete(GuildLogFeatures._VALID_LOG_FEATURES)
                )
            ]
    ):
        """Disables a feature."""
        await ctx.defer(ephemeral=True)
        feature = feature.lower()
        if feature not in GuildLogFeatures._VALID_LOG_FEATURES:
            return await ctx.respond(f"\N{cross mark} The feature `{feature}` does not exist.")

        await self._set_log_feature(ctx.guild_id, feature, False, user_id=ctx.user.id)
        await ctx.respond(
            f"\N{white heavy check mark} Disabled the feature `{feature}`."
        )


def setup(bot):
    bot.add_cog(SettingsCog(bot))
