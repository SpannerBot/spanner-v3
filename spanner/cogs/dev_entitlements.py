import datetime
import logging

import discord
from discord.ext import commands, bridge
from spanner.share.database import Premium
from spanner.share.config import load_config
from spanner.share.views.confirm import ConfirmView
from spanner.share.views.premium import PremiumRequired
from spanner.share.utils import entitled_to_premium


class DevEntitlementCog(commands.Cog):
    def __init__(self, bot):
        self.bot: bridge.Bot = bot
        self.log = logging.getLogger("spanner.cogs.dev_entitlements")

    @staticmethod
    def get_premium_view(ctx: discord.ApplicationContext | commands.Context) -> PremiumRequired | None:
        subscription_sku = load_config()["skus"]["subscription_id"]
        if not subscription_sku:
            logging.getLogger("spanner.cogs.dev_entitlements").warning(
                "No subscription SKU configured in the bot configuration. Set `skus.subscription_id`."
            )
            view = None
        else:
            view = PremiumRequired(ctx, subscription_sku)
        return view

    async def send_log_message(self, content: str = None, embed: discord.Embed = None) -> discord.Message | None:
        if not content and not embed:
            return
        cfg = load_config()["cogs"]["meta"].get("support_guild_id")
        if not cfg:
            return
        guild = self.bot.get_guild(cfg)
        if not guild:
            return
        channel = discord.utils.get(guild.text_channels, name="bot-logs")
        if not channel or not channel.can_send():
            return
        return await channel.send(content=content, embed=embed)

    @commands.group(name="entitlements", aliases=['ent'], invoke_without_command=True)
    @commands.is_owner()
    async def entitlements(self, ctx):
        """entitlements management"""
        return

    @entitlements.command(name="list")
    @commands.is_owner()
    async def list_entitlements(
            self,
            ctx: commands.Context,
            user: discord.User | None = None,
            sku_ids: commands.Greedy[int] = None,
            guild_id: int | None = None,
            exclude_ended: bool | None = False
    ):
        """Lists all entitlements enabled for the app"""
        if sku_ids:
            sku_ids = list(map(discord.Object, sku_ids))
        if guild_id:
            guild_id = discord.Object(guild_id)
        entitlements = self.bot.entitlements(
            user=user,
            skus=sku_ids,
            guild=guild_id,
            exclude_ended=exclude_ended
        )
        paginator = commands.Paginator()

        async for entitlement in entitlements:
            paginator.add_line(
                "{0.id} - sku_id={0.sku_id!r} user_id={0.user_id!r} type={0.type!r} deleted={0.deleted!r} "
                "starts_at={0.starts_at!r} ends_at={0.ends_at!r} guild_id={0.guild_id!r} "
                "consumed={0.consumed!r}".format(entitlement),
                empty=True
            )

        if not paginator.pages:
            return await ctx.reply("No entitlements found.")
        for page in paginator.pages:
            await ctx.reply(page)

    @entitlements.command(name="create")
    @commands.is_owner()
    async def create_test_entitlement(
            self,
            ctx: commands.Context,
            sku_id: int,
            owner: int | discord.User
    ):
        """Creates a test entitlement"""
        if isinstance(owner, int):
            owner = self.bot.get_user(owner) or self.bot.get_guild(owner)

        if isinstance(owner, discord.User):
            owner_type = 2  # user
        else:
            owner_type = 1  # guild

        sku = discord.utils.get(await self.bot.fetch_skus(), id=sku_id)
        if not sku:
            return await ctx.reply("SKU not found.")
        sku_id = sku.id

        try:
            entitlement = await self.bot.http.create_test_entitlement(
                self.bot.user.id,
                dict(
                    sku_id=sku_id,
                    owner_id=owner.id,
                    owner_type=owner_type
                )
            )
        except discord.HTTPException as e:
            return await ctx.reply(f"Failed to create entitlement: {e!r}")
        return await ctx.reply(f"Entitlement created: {entitlement!r}")

    @entitlements.command(name="delete")
    @commands.is_owner()
    async def delete_test_entitlement(
            self,
            ctx: commands.Context,
            entitlement_id: int
    ):
        """Deletes a test entitlement"""
        try:
            await self.bot.http.delete_test_entitlement(self.bot.user.id, entitlement_id)
        except discord.HTTPException as e:
            return await ctx.reply(f"Failed to delete entitlement: {e!r}")
        return await ctx.reply("Entitlement deleted.")

    @commands.group(name="skus", aliases=['sku'], invoke_without_command=True)
    @commands.is_owner()
    async def skus(self, ctx):
        """SKU management"""
        return

    @skus.command(name="list")
    @commands.is_owner()
    async def list_skus(self, ctx: commands.Context):
        """Lists all SKUs available."""
        try:
            skus = await self.bot.fetch_skus()
        except discord.HTTPException as e:
            return await ctx.reply(f"Failed to fetch SKUs: {e!r}")
        paginator = commands.Paginator()

        for sku in skus:
            paginator.add_line(
                "{0.id} - name={0.name!r} type={0.type!r} slug={0.slug!r} flags={1}".format(
                    sku,
                    dict(sku.flags)
                ),
                empty=True
            )

        if not paginator.pages:
            return await ctx.reply("No SKUs found.")
        for page in paginator.pages:
            await ctx.reply(page)

    @commands.group(name="free-trial", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=True)
    async def free_trial(self, ctx: commands.Context):
        """Activates a free trial of the premium service."""
        already_entitled = await entitled_to_premium(ctx.guild, allow_trial=False)
        if already_entitled:
            return await ctx.reply(
                f"\N{cross mark} This server is already entitled to premium features.",
                view=None
            )
        now = discord.utils.utcnow()
        view = self.get_premium_view(ctx)

        if (trial := await Premium.get_or_none(guild_id=ctx.guild.id)) is not None:
            if trial.is_expired:
                return await ctx.reply(
                    f"\N{cross mark} Your free trial expired {discord.utils.format_dt(trial.end, 'R')}.",
                    view=view
                )
            else:
                return await ctx.reply(
                    f"\U000026a0\U0000fe0f This server's free trial is already active, and expires "
                    f"{discord.utils.format_dt(trial.end, 'R')}.",
                    view=view
                )
        else:
            msg, confirm = await ConfirmView(
                ctx.author,
                "Are you sure you want to activate a free trial? "
                "This cannot be undone and can only be done once per server."
            ).ask(ctx, just_result=False)
            if confirm is False:
                return await msg.edit(content="\N{cross mark} Will not activate free trial.")
            await msg.edit("<a:loading:923665831345418241> Activating free trial...", view=None)
            try:
                trial = await Premium.create(
                    user_id=ctx.author.id,
                    guild_id=ctx.guild.id,
                    start=now,
                    end=now + datetime.timedelta(days=30)
                )
            except Exception as e:
                await msg.edit(content=f"\N{cross mark} Failed to activate free trial: {e!r}")
                raise
            else:
                await msg.edit(
                    content=f"\N{white heavy check mark} Free trial activated! "
                            f"Expires {discord.utils.format_dt(trial.end, 'R')}.",
                    view=view
                )

    @free_trial.command(name="info")
    async def free_trial_info(self, ctx: commands.Context, guild_id: int = None):
        """Displays information about a free trial.

        the [guild_id] parameter can only be used by the bot owner."""
        if guild_id is not None and not await self.bot.is_owner(ctx.author):
            return await ctx.reply("\N{cross mark} You are not allowed to check other guild's premium trial status.")
        guild_id = guild_id or ctx.guild.id
        trial = await Premium.get_or_none(guild_id=guild_id)
        if trial is None:
            return await ctx.reply("\N{cross mark} No free trial found.")
        return await ctx.reply(
            "Free trial information for {0.name!r}:\n"
            "* ID: `{1.id!s}`\n"
            "* Started by: `{1.user_id}`\n"
            "* For server: `{1.guild_id}`\n"
            "* Started at: {2}\n"
            "* Expires at: {3}\n"
            "* Is expired: {1.is_expired!s}".format(
                ctx.guild,
                trial,
                discord.utils.format_dt(trial.start, "R"),
                discord.utils.format_dt(trial.end, "R")
            )
        )

    @free_trial.command(name="grant", aliases=["gift"])
    @commands.is_owner()
    async def free_trial_grant(self, ctx: commands.Context, guild_id: int = None, days: int = 30):
        """Grants a server a free trial, or renews an existing one."""
        guild_id = guild_id or ctx.guild.id
        now = discord.utils.utcnow()
        trial, _ = await Premium.update_or_create(
            guild_id=guild_id,
            defaults=dict(
                user_id=ctx.author.id,
                start=now,
                end=now + datetime.timedelta(days=days)
            )
        )
        return await ctx.reply(
            f"\N{white heavy check mark} Free trial granted to {guild_id}. "
            f"Expires {discord.utils.format_dt(trial.end, 'R')}."
        )

    @free_trial.command(name="expire", aliases=["end", "delete"])
    @commands.is_owner()
    async def free_trial_delete(self, ctx: commands.Context, guild_id: int = None):
        """Deletes a free trial of the premium service."""
        guild_id = guild_id or ctx.guild.id
        trial = await Premium.get_or_none(guild_id=guild_id)
        if trial is None:
            return await ctx.reply("\N{cross mark} No free trial found.")
        trial.end = discord.utils.utcnow()
        await trial.save()
        return await ctx.reply("\N{white heavy check mark} Free trial expired.")

    @free_trial.command(name="test", aliases=["check"])
    @commands.is_owner()
    async def free_trial_test(self, ctx: commands.Context, guild_id: int = None, allow_trial: bool = False):
        """
        Checks whether premium (or trial) features are enabled for a server.

        If [allow_trial] is set to True, the server will be considered entitled to premium features if it has a trial.
        """
        guild_id = guild_id or ctx.guild.id
        guild = self.bot.get_guild(guild_id)
        if not await entitled_to_premium(guild, allow_trial=allow_trial):
            existing_trial = await Premium.get_or_none(guild_id=guild_id)
            if existing_trial:
                return await ctx.reply(
                    "\N{cross mark} This server's free trial expired.",
                    view=self.get_premium_view(ctx)
                )
            return await ctx.reply(
                "\N{cross mark} This server is not entitled to premium features.",
                view=self.get_premium_view(ctx)
            )
        else:
            return await ctx.reply(
                "\N{white heavy check mark} This server is entitled to premium features."
            )


def setup(bot):
    bot.add_cog(DevEntitlementCog(bot))
