import discord
from discord.ext import commands


class PremiumRequired(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext | commands.Context, sku_id: int):
        self.ctx = ctx
        super().__init__(timeout=300)
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.premium,
                sku_id=sku_id,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.ctx.author.id:
            return True
        return False
