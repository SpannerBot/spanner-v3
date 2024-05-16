import discord


__all__ = ("GenericLabelledEmbedView",)


class GenericLabelledEmbedView(discord.ui.View):
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

    @property
    def current_embed(self):
        for child in self.children:
            if isinstance(child, self.EmbedSwitchButton):
                if child.disabled:
                    return child.embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.ctx.user.id