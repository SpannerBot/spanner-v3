import discord


class PruneFilterView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, *, v: str = "100"):
        super().__init__(timeout=300, disable_on_timeout=True)
        self.ctx = ctx

        self.prune_pinned = True
        self.prune_only_bots = False
        self.prune_only_humans = False
        self.prune_members = []

    @property
    def v(self) -> str:
        m = {True: "1", False: "0"}
        return f"{m[self.prune_pinned]}{m[self.prune_only_bots]}{m[self.prune_only_humans]}"

    def __repr__(self):
        return f"PruneFilter(v={self.v!r})"

    def check(self, message: discord.Message) -> bool:
        if self.prune_pinned is False and message.pinned:
            return False
        if self.prune_only_bots and message.author.bot:
            return True
        if self.prune_only_humans and not message.author.bot:
            return True
        if self.prune_members and message.author.id not in self.prune_members:
            return False
        return True

    def _update_view(self):
        for child in self.children:
            if isinstance(child, discord.Button):
                try:
                    enabled = getattr(self, 'prune_%s' % child.label.lower())
                except AttributeError:
                    enabled = getattr(self, child.custom_id, None)
                    if enabled is None:
                        continue

                if enabled:
                    child.style = discord.ButtonStyle.green
                else:
                    child.style = discord.ButtonStyle.red

    @discord.ui.button(label="Pinned", style=discord.ButtonStyle.green)
    async def on_pinned(self, _, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True)
        self.prune_pinned = not self.prune_pinned
        self._update_view()
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Bots", custom_id="only_bots", style=discord.ButtonStyle.red)
    async def on_bots(self, _, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True)
        self.prune_only_bots = not self.prune_only_bots
        self.prune_only_humans = not self.prune_only_bots
        self._update_view()
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Only humans", custom_id="only_humans", style=discord.ButtonStyle.red)
    async def on_humans(self, _, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True)
        self.prune_only_humans = not self.prune_only_humans
        self.prune_only_bots = not self.prune_only_humans
        self._update_view()
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Prune", custom_id="prune")
    async def on_prune(self, _, interaction: discord.Interaction):
        await interaction.response.defer(invisible=True)
        self.disable_all_items()
        await interaction.edit_original_response(view=self)
        self.stop()
