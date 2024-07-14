import discord

from spanner.share.database import GuildAuditLogEntry, GuildConfig, GuildNickNameModeration


class NicknameFilterManager(discord.ui.View):
    def __init__(self, config: GuildConfig):
        super().__init__()
        self.guild_config = config

    @discord.ui.select(
        placeholder="Select the enabled filters.",
        custom_id="filters",
        min_values=0,
        max_values=len(GuildNickNameModeration.CATEGORIES),
        options=[
            discord.SelectOption(label=key, description=value)
            for key, value in GuildNickNameModeration.CATEGORIES.items()
        ],
    )
    async def select_filters(self, select: discord.ui.Select, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True)
        config, _ = await GuildNickNameModeration.get_or_create(guild_id=interaction.guild.id)
        changes = []
        for key in GuildNickNameModeration.CATEGORIES.keys():
            new = key in select.values
            current = getattr(config, key)
            if new == current:
                continue

            if new:
                changes.append(f"\N{WHITE HEAVY CHECK MARK} {key}")
                await GuildAuditLogEntry.create(
                    guild=self.guild_config,
                    author=interaction.user.id,
                    namespace="settings.nickname_filters",
                    action="enable",
                    description=f"Enabled the {key!r} filter",
                )
            else:
                changes.append(f"\N{CROSS MARK} {key}")
                await GuildAuditLogEntry.create(
                    guild=self.guild_config,
                    author=interaction.user.id,
                    namespace="settings.nickname_filters",
                    action="disable",
                    description=f"Disabled the {key!r} filter",
                )

            setattr(config, key, key in select.values)
        await config.save()
        await interaction.followup.send("\n".join(changes or ["No changes made."]), ephemeral=True)

    @discord.ui.button(label="Disable All", style=discord.ButtonStyle.danger)
    async def disable_all(self, _, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True)
        config = await GuildNickNameModeration.get_or_none(guild_id=interaction.guild.id)
        if config:
            await config.delete()
            await GuildAuditLogEntry.create(
                guild=self.guild_config,
                author=interaction.user.id,
                namespace="settings.nickname_filters",
                action="disable.all",
                description="Disabled all filters",
            )
        await interaction.followup.send("\N{CROSS MARK} Disabled all filters.", ephemeral=True)
