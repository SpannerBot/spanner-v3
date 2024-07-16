import discord
from discord.ext import commands, bridge


class DevEntitlementCog(commands.Cog):
    def __init__(self, bot):
        self.bot: bridge.Bot = bot

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


def setup(bot):
    bot.add_cog(DevEntitlementCog(bot))
