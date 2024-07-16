import discord
from discord.ext import commands, bridge


class DevEntitlementCog(commands.Cog):
    def __init__(self, bot):
        self.bot: bridge.Bot = bot

    @commands.group(name="entitlements", aliases=['ent'], invoke_without_command=True)
    @commands.is_owner()
    async def entitlements(self, ctx):
        return

    @entitlements.command(name="list")
    @commands.is_owner()
    async def list_entitlements(
            self,
            ctx: commands.Context,
            user: discord.User | None = None,
            sku_ids: commands.Greedy[int] | None = None,
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
                "{0.id} - sku_id={0.sku_id!r} user_id={0.user_id!r} type={0.type.name!r} deleted={0.deleted!r} "
                "starts_at={0.starts_at!r} ends_at={0.ends_at!r} guild_id={0.guild_id!r} "
                "consumed={0.consumed!r}".format(entitlement)
            )

        if not paginator.pages:
            return await ctx.send("No entitlements found.")
        for page in paginator.pages:
            await ctx.send(page)

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
            owner_type = "user"
        else:
            owner_type = "guild"

        sku = discord.utils.get(await self.bot.fetch_skus(), id=sku_id)
        if not sku:
            return await ctx.reply("SKU not found.")
        sku_id = sku.id

        entitlement = await self.bot.http.create_test_entitlement(
            self.bot.user.id,
            discord.monetization.CreateTestEntitlementPayload(
                sku_id=sku_id,
                owner_id=owner.id,
                owner_type=owner_type
            )
        )
        return await ctx.reply(f"Entitlement created: {entitlement!r}")

    @entitlements.command(name="delete")
    @commands.is_owner()
    async def delete_test_entitlement(
            self,
            ctx: commands.Context,
            entitlement_id: int
    ):
        """Deletes a test entitlement"""
        await self.bot.http.delete_test_entitlement(self.bot.user.id, entitlement_id)
        return await ctx.reply("Entitlement deleted.")

    @commands.group(name="skus", aliases=['sku'], invoke_without_command=True)
    @commands.is_owner()
    async def skus(self, ctx):
        return

    @skus.command(name="list")
    @commands.is_owner()
    async def list_skus(self, ctx: commands.Context):
        """Lists all SKUs available."""
        skus = await self.bot.fetch_skus()
        paginator = commands.Paginator()

        for sku in skus:
            paginator.add_line(
                "{0.id} - name={0.name!r} type={0.type.name!r} slug={0.slug!r} flags={1}".format(
                    sku,
                    dict(sku.flags)
                )
            )

        if not paginator.pages:
            return await ctx.send("No SKUs found.")
        for page in paginator.pages:
            await ctx.send(page)


def setup(bot):
    bot.add_cog(DevEntitlementCog(bot))
