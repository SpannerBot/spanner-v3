import discord
from discord.ext import commands

from spanner.share.config import load_config


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

    @discord.ui.button(label="Restore Purchases", style=discord.ButtonStyle.secondary, custom_id="restore_purchases")
    async def _restore_purchases(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("\N{CROSS MARK} You can only use this in a server.", ephemeral=True)

        button.disabled = True
        await interaction.response.defer(ephemeral=True)
        from spanner.share.database import Premium

        config = load_config()
        if not (_sku_id := config["skus"].get("subscription_id")):
            sku = None
            sku_check = lambda e: e.type == 5
        else:
            sku = discord.Object(_sku_id)
            sku_check = lambda e: e.sku_id == sku.id
        entitlements = await interaction.guild.entitlements(skus=[sku] if sku else None, exclude_ended=True).flatten()
        if not entitlements:
            await interaction.followup.send(
                "\N{CROSS MARK} No active premium subscription for this server found.",
            )
            await interaction.edit_original_response(view=self)
            return

        for entitlement in entitlements:
            if entitlement.guild_id == interaction.guild.id and sku_check(entitlement):
                await Premium.from_entitlement(entitlement)
                await interaction.followup.send(
                    "\N{WHITE HEAVY CHECK MARK} Premium restored successfully. Re-try your previous action.",
                )
                return

        support = self.ctx.bot.get_application_command("support")
        if support:
            support = "</support:%d>" % support.id
        else:
            support = "support"
        await interaction.followup.send(
            "\N{CROSS MARK} No valid premium subscription for this server found. If you think this is incorrect,"
            f"please contact {support}.",
        )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.ctx.author.id:
            return True
        return False
