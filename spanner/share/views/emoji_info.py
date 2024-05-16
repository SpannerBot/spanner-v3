import asyncio
import logging

import discord


__all__ = ("EditEmojiRolesView",)


class EditEmojiRolesView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, emoji: discord.Emoji):
        super().__init__(timeout=600, disable_on_timeout=True)
        self.ctx = ctx
        self.emoji = emoji
        self.chosen_roles = []
        self.log = logging.getLogger("share.views.emoji_info.EditEmojiRolesView")
        self.lock = asyncio.Lock()

    @discord.ui.role_select(
        placeholder="Choose authorised roles",
        min_values=0,
        max_values=25,
        custom_id="role_select",
    )
    async def role_select(self, select: discord.ui.Select, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, invisible=True)
        self.chosen_roles = select.values

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.primary, custom_id="save")
    async def save(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True, ephemeral=True)
        async with self.lock:
            self.disable_all_items()
            button.label = "Applying..."
            button.style = discord.ButtonStyle.secondary

            try:
                await self.emoji.edit(
                    name=self.emoji.name,
                    roles=self.chosen_roles,
                    reason=f"Roles updated by {interaction.user}",
                )
            except discord.HTTPException as e:
                self.log.error(f"Failed to update roles for {self.emoji}.", exc_info=e)
                button.label = "Error while applying"
                button.style = discord.ButtonStyle.danger
                button.emoji = discord.PartialEmoji.from_str("\N{crying face}")
                await interaction.edit_original_response(view=self)
            else:
                button.label = "Applied"
                button.style = discord.ButtonStyle.success
                await interaction.edit_original_response(view=self)

            await asyncio.sleep(5)
            button.label = "Apply"
            button.style = discord.ButtonStyle.primary
            self.enable_all_items()
            await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel")
    async def cancel(self, _, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True, ephemeral=True)
        async with self.lock:
            self.disable_all_items()
            await interaction.edit_original_response(view=self)
            self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.user.id
