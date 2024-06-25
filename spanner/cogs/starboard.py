import asyncio
import io
import textwrap

import discord
from discord.ext import commands
from tortoise.transactions import in_transaction
from spanner.share.database import StarboardEntry, StarboardConfig, StarboardMode, GuildAuditLogEntry, GuildConfig


class StarboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.starboard_cache: dict[discord.Message, int] = {}

    @staticmethod
    async def count_reactions(message: discord.Message, emoji: str, exclude_bots: bool = True) -> int:
        count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji:
                async for user in reaction.users():
                    if exclude_bots and user.bot:
                        continue
                    count += 1
        return count

    async def get_or_fetch_message(self, channel_id: int, message_id: int) -> discord.Message:
        """
        Fetches a message from cache where possible, falling back to the API.
        """
        message: discord.Message | None = discord.utils.get(self.bot.cached_messages, id=message_id)
        if not message:
            message: discord.Message = await self.bot.get_channel(channel_id).fetch_message(message_id)
        return message

    async def generate_starboard_embed(
            self,
            message: discord.Message,
            config: StarboardConfig
    ) -> tuple[list[discord.Embed], int]:
        """
        Generates an embed ready for a starboard message.

        :param message: The message to base off of.
        :param config: The starboard configuration.
        :return: The created embed
        """
        star_count = self.starboard_cache.get(message, 0)
        star_emoji_count = (config.star_emoji * min(10, star_count))

        embed = discord.Embed(
            colour=discord.Colour.gold(),
            url=message.jump_url,
            timestamp=message.created_at,
            author=discord.EmbedAuthor(
                message.author.display_name,
                message.author.jump_url,
                message.author.display_avatar.url
            ),
            fields=[
                discord.EmbedField(
                    name="Info",
                    value=f"[Stars: {star_emoji_count} ({star_count:,})]({message.jump_url})"
                )
            ]
        )
        if message.reference:
            try:
                ref_message = await self.get_or_fetch_message(message.reference.channel_id, message.reference.message_id)
            except discord.HTTPException:
                pass
            else:
                text = ref_message.content.splitlines()[0]
                v = f"[{ref_message.author.mention}'s message: ]({ref_message.jump_url})"
                remaining = 1024 - len(v)
                t = textwrap.shorten(text, remaining, placeholder="...")
                v = f"[{ref_message.author.display_name}'s message: {t}]({ref_message.jump_url})"
                embed.add_field(
                    name="Replying to",
                    value=v
                )
        elif message.interaction:
            if message.interaction.type == discord.InteractionType.application_command:
                real_author: discord.User = await discord.utils.get_or_fetch(
                    self.bot,
                    "user",
                    int(message.interaction.data["user"]["id"])
                )
                real_author = await discord.utils.get_or_fetch(
                    message.guild,
                    "member",
                    real_author.id,
                    default=real_author
                ) or message.author
                embed.set_author(
                    name=real_author.display_name,
                    icon_url=real_author.display_avatar.url,
                    url=real_author.jump_url
                )
                embed.add_field(
                    name="Interaction",
                    value=f"Command `/{message.interaction.data['name']}` of {message.author.mention}"
                )

        if message.content:
            embed.description = message.content
        elif message.embeds:
            for message_embed in message.embeds:
                if message_embed.type != "rich":
                    if message_embed.type == "image":
                        if message_embed.thumbnail and message_embed.thumbnail.proxy_url:
                            embed.set_image(url=message_embed.thumbnail.proxy_url)
                    continue
                if message_embed.description:
                    embed.description = message_embed.description
        elif not message.attachments:
            raise ValueError("Message does not appear to contain any text, embeds, or attachments.")

        if message.attachments:
            new_fields = []
            for n, attachment in reversed(tuple(enumerate(message.attachments, start=1))):
                attachment: discord.Attachment
                if attachment.size >= 1024 * 1024:
                    size = f"{attachment.size / 1024 / 1024:,.1f}MiB"
                elif attachment.size >= 1024:
                    size = f"{attachment.size / 1024:,.1f}KiB"
                else:
                    size = f"{attachment.size:,} bytes"
                new_fields.append(
                    {
                        "name": "Attachment #%d:" % n,
                        "value": f"[{attachment.filename} ({size})]({attachment.url})",
                        "inline": True
                    }
                )
                if attachment.content_type.startswith("image/"):
                    embed.set_image(url=attachment.url)
            new_fields.reverse()
            for field in new_fields:
                embed.add_field(**field)
            # This whacky reverse -> perform -> reverse basically just means we can set the first image/*
            # attachment as the image.

        return [embed, *filter(lambda e: e.type == "rich", message.embeds)], star_count

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        source_channel: discord.abc.Messageable | None = guild.get_channel(payload.channel_id)
        if not source_channel:
            return
        try:
            message = await source_channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if message.author.bot:
            return

        config = await StarboardConfig.get_or_none(guild__id=payload.guild_id)
        if not config:
            return
        if str(payload.emoji) != config.star_emoji:
            return
        starboard_channel: discord.TextChannel | None = guild.get_channel(config.channel_id)
        if not starboard_channel:
            return
        elif not starboard_channel.can_send(discord.Embed, discord.File):
            return
        await config.fetch_related("guild")

        if message not in self.starboard_cache:
            self.starboard_cache[message] = await self.count_reactions(message, config.star_emoji)
        else:
            self.starboard_cache[message] += 1

    starboard_group = discord.SlashCommandGroup(name="starboard", description="Manage the starboard settings")

    @starboard_group.command(name="set-channel")
    @discord.default_permissions(manage_channels=True, manage_messages=True)
    async def set_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        """Sets up a starboard channel"""
        await ctx.defer()
        if not channel.can_send(discord.Embed, discord.File):
            return await ctx.respond(
                "\N{cross mark} I need `send messages`, `embed links`, and `attach files` permissions in "
                f"{channel.mention}. Please change the permissions, and try again.",
                ephemeral=True,
                delete_after=60
            )
        _emoji = discord.PartialEmoji.from_str("\N{WHITE MEDIUM STAR}")
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
                ),
                silent=True
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
        async with in_transaction() as conn:
            gc, _ = await GuildConfig.get_or_create(id=ctx.guild.id)
            config, _ = await StarboardConfig.get_or_create(
                guild=gc,
                defaults={
                    "channel_id": channel.id,
                    "star_emoji": str(_emoji)
                }
            )
            config.channel_id = channel.id
            config.star_emoji = str(_emoji)
            await config.save(using_db=conn)
            await GuildAuditLogEntry.create(
                using_db=conn,
                guild=gc,
                author=ctx.user.id,
                namespace="settings.starboard",
                action="set_channel",
                description=f"Set the starboard channel to {channel.mention}"
            )
            await GuildAuditLogEntry.create(
                using_db=conn,
                guild=gc,
                author=ctx.user.id,
                namespace="settings.starboard",
                action="set_emoji",
                description=f"Set the starboard emoji to {_emoji}"
            )
            await ctx.respond(f"\N{WHITE HEAVY CHECK MARK} Starboard channel set to {channel.mention}.")

    @starboard_group.command(name="set-emoji")
    @discord.default_permissions(manage_channels=True, manage_messages=True)
    @commands.bot_has_permissions(add_reactions=True, manage_messages=True)
    async def set_emoji(self, ctx: discord.ApplicationContext):
        """Sets the emoji used to star messages"""
        async with in_transaction() as conn:
            await ctx.defer()
            config = await StarboardConfig.get_or_none(guild__id=ctx.guild.id, using_db=conn)
            if not config:
                return await ctx.respond(
                    "You need to set up a starboard channel first. Use `/starboard set-channel` to set up a "
                    "starboard channel.",
                    ephemeral=True
                )
            m = await ctx.respond(
                "React to this message with the emoji you want to use as the starboard emoji.",
            )
            try:
                reaction, _ = await self.bot.wait_for(
                    "reaction_add",
                    check=lambda r, u: r.message.id == m.id and u.id == ctx.user.id,
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                return await ctx.edit(content="You took too long to react.")
            await m.clear_reactions()
            try:
                await m.add_reaction(reaction.emoji)
            except discord.HTTPException as e:
                return await ctx.edit(content=f"Failed to add the star reaction. Error: `{e}`")
            config.star_emoji = str(reaction.emoji)
            await config.save(conn)
            gc, _ = await GuildConfig.get_or_create(id=ctx.guild.id)
            await GuildAuditLogEntry.create(
                conn,
                guild=gc,
                author=ctx.user.id,
                namespace="settings.starboard",
                action="set_emoji",
                description=f"Set the starboard emoji to {reaction.emoji}"
            )
            await ctx.edit(content=f"Starboard emoji set to {reaction.emoji}")
            await m.clear_reactions()


def setup(bot):
    bot.add_cog(StarboardCog(bot))
