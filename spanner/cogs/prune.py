import typing

import discord
from discord.ext import commands, bridge

from spanner.share.views.prune import PruneFilterView
from spanner.share.utils import SilentCommandError


class PruneCog(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot

    @commands.slash_command()
    @discord.commands.default_permissions(
        manage_messages=True
    )
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    @commands.max_concurrency(1, per=commands.BucketType.channel)
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def prune(
            self,
            ctx: discord.ApplicationContext,
            limit: typing.Annotated[
                int,
                discord.Option(
                    discord.SlashCommandOptionType.integer,
                    description="The number of messages to delete.",
                    required=True,
                    min_value=1,
                    max_value=1000
                )
            ],
            enable_filters: typing.Annotated[
                bool,
                discord.Option(
                    name="filters",
                    description="Shows the message filter selector.",
                    required=False,
                    default=False
                )
            ]
    ):
        """Prunes a number of messages from the channel, optionally filtering them."""
        await ctx.defer(ephemeral=True)

        filters = PruneFilterView(ctx)
        if enable_filters:
            await ctx.respond("Select the filters you want to apply.", view=filters)
            await filters.wait()
            await ctx.delete(delay=0.1)

        await ctx.respond("Pruning messages (this may take some time)...", ephemeral=True)

        try:
            n = await ctx.channel.purge(
                limit=limit,
                check=filters.check,
                reason=f"{ctx.user} requested a prune of {limit} messages with filters {filters.v!r}"
            )
        except discord.HTTPException as e:
            await ctx.edit(
                content=None,
                embed=discord.Embed(
                    title="Sorry, there was an error while pruning messages.",
                    description=f"Messages may or not have been deleted. Error: {e}\n"
                                f"The developer has been notified.",
                    color=discord.Color.red()
                )
            )
            raise SilentCommandError from e
        else:
            await ctx.edit(
                content=f"Successfully pruned {len(n):,} messages.",
                embed=None
            )


def setup(bot: bridge.Bot):
    bot.add_cog(PruneCog(bot))
