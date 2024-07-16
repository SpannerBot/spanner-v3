import typing

import discord
from discord.ext import commands


class ConfirmView(discord.ui.View):
    """
    Asks the user to confirm they want to proceed with the action.
    """

    def __init__(
        self,
        user: discord.User | discord.Member | discord.Object,
        question: str,
        *,
        title: str | None = "Are you sure?",
        timeout: int = 30,
    ):
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.user = user
        self.embed = discord.Embed(
            title=title,
            description=question + f"\n\n*Please answer within {timeout:,} seconds.*",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def yes(self, _, interaction: discord.Interaction):
        self.confirmed = True
        self.disable_all_items()
        await interaction.response.edit_message(embed=self.embed, view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def no(self, _, interaction: discord.Interaction):
        self.disable_all_items()
        await interaction.response.edit_message(embed=self.embed, view=self)
        self.stop()

    @typing.overload
    async def ask(
        self, ctx: discord.ApplicationContext | commands.Context, just_result: typing.Literal[False]
    ) -> tuple[discord.InteractionResponse | discord.WebhookMessage | discord.Message, bool]: ...

    @typing.overload
    async def ask(
        self, ctx: discord.ApplicationContext | commands.Context, just_result: typing.Literal[True] = True
    ) -> bool: ...

    async def ask(
        self, ctx: discord.ApplicationContext | commands.Context, just_result: bool = True
    ) -> bool | tuple[discord.InteractionResponse | discord.WebhookMessage, bool]:
        rm = ctx.respond if isinstance(ctx, discord.ApplicationContext) else ctx.reply
        x = await rm(embed=self.embed, view=self)
        await self.wait()
        if just_result:
            return self.confirmed
        return x, self.confirmed
