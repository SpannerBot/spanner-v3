import io

import discord
from discord.ext import commands
from spanner.share.database import StarboardEntry, StarboardConfig, StarboardMode, GuildAuditLogEntry, GuildConfig


class StarboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    starboard_group = discord.SlashCommandGroup(name="starboard", description="Manage the starboard settings")

    @starboard_group.command(name="set-channel")
    @discord.default_permissions(manage_channels=True, manage_messages=True)
    async def set_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        """Sets up a starboard channel"""
        await ctx.defer()
        gc, _ = await GuildConfig.get_or_create(id=ctx.guild.id)
        config, _ = await StarboardConfig.get_or_create(guild__id=gc.id)

        if not channel.can_send(discord.Embed, discord.File):
            return await ctx.respond(
                "\N{cross mark} I need `send messages`, `embed links`, and `attach files` permissions in "
                f"{channel.mention}. Please change the permissions, and try again.",
                ephemeral=True,
                delete_after=60
            )

        _emoji = discord.PartialEmoji.from_str(config.star_emoji)
        try:
            m = await channel.send(
                "This channel has been set as a starboard channel. Test message.",
                embed=discord.Embed(
                    title="This channel is a starboard channel.",
                    description="This message is a test message to ensure that the starboard is working correctly.",
                    colour=discord.Colour.gold(),
                    timestamp=discord.utils.utcnow(),
                    author=discord.EmbedAuthor(name=ctx.user.display_name, icon_url=ctx.user.display_avatar.url),
                    image="attachment://avatar.png"
                ),
                file=discord.File(
                    io.BytesIO(await ctx.me.display_avatar.with_format("png").read()),
                    filename="avatar.png"
                )
            )
        except discord.HTTPException as e:
            return await ctx.respond(
                f"\N{CROSS MARK} Failed to send message in {channel.mention}. Error: `{e}`",
            )

        try:
            await m.add_reaction(_emoji)
        except discord.HTTPException as e:
            return await ctx.respond(
                f"\N{CROSS MARK} Failed to add the star reaction to [the test message]({m.jump_url}). Error: `{e}`",
            )
        await m.remove_reaction(_emoji, ctx.me)
        await m.delete()
        config.channel_id = channel.id
        config.star_emoji = str(_emoji)
        await config.save()
        await GuildAuditLogEntry.create(
            guild=gc,
            author=ctx.user.id,
            namespace="settings.starboard",
            action="set_channel",
            description=f"Set the starboard channel to {channel.mention}"
        )
        await GuildAuditLogEntry.create(
            guild=gc,
            author=ctx.user.id,
            namespace="settings.starboard",
            action="set_emoji",
            description=f"Set the starboard emoji to {_emoji}"
        )
        await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Starboard channel set to {channel.mention}.")


def setup(bot):
    bot.add_cog(StarboardCog(bot))
