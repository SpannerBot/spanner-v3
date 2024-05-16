import logging
import typing

import discord
from discord.ext import commands

from spanner.share.utils import get_bool_emoji, hyperlink
from spanner.share.views import GenericLabelledEmbedView


class EmojiStealButton(discord.ui.Button):
    view: GenericLabelledEmbedView

    def __init__(self, emoji: discord.Emoji | discord.PartialEmoji):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="Steal",
            custom_id="steal",
            emoji=emoji
        )
        self._emoji = emoji
        self.log = logging.getLogger("cogs.emoji_info.EmojiStealView")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, invisible=True)
        self.disabled = True
        self.label = "Stealing..."
        await interaction.edit_original_response(view=self.view)

        try:
            # Workaround for 'discord.errors.DiscordException: Invalid state (no ConnectionState provided)'
            # noinspection PyProtectedMember
            body: bytes = await self.view.ctx.bot.http.get_from_cdn(self.emoji.url)
        except (discord.HTTPException, ConnectionError) as e:
            self.log.error(
                f"Failed to download emoji {self.emoji.name} from {self.emoji.url} in guild {interaction.guild.id}.",
                exc_info=e,
            )
            self.label = "Error while downloading"
            self.emoji = discord.PartialEmoji.from_str("\N{crying face}")
            self.style = discord.ButtonStyle.red
            return await interaction.edit_original_response(view=self.view)
        else:
            if len(body) > 500 * 1024:
                self.label = "Emoji too big"
                self.emoji = discord.PartialEmoji.from_str("\N{no entry}")
                self.style = discord.ButtonStyle.red
                return await interaction.edit_original_response(view=self.view)
            else:
                self.label = "Creating emoji..."
                await interaction.edit_original_response(view=self.view)
                try:
                    await self.view.ctx.guild.create_custom_emoji(
                        name=self.emoji.name,
                        image=body,
                        reason=f"Emoji stolen by {interaction.user}",
                    )
                except discord.HTTPException as e:
                    self.log.error(
                        f"Failed to create emoji {self.emoji.name} in guild {interaction.guild.id}.",
                        exc_info=e,
                    )
                    self.label = "Error while creating"
                    self.emoji = discord.PartialEmoji.from_str("\N{crying face}")
                    self.style = discord.ButtonStyle.red
                    return await interaction.edit_original_response(view=self.view)
                else:
                    self.label = "Emoji stolen!"
                    self.emoji = discord.PartialEmoji.from_str("\N{white heavy check mark}")
                    self.style = discord.ButtonStyle.green
                    return await interaction.edit_original_response(view=self.view)


class EmojiInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def get_partial_emoji_info(emoji: discord.PartialEmoji):
        emoji_info = [
            f"**ID:** `{emoji.id}`",
            f"**Name:** `{emoji.name}`",
            f"**Is animated?** {get_bool_emoji(emoji.animated)}",
            f"**Is custom?** {get_bool_emoji(emoji.is_custom_emoji())}",
            f"**Is regular unicode?** {get_bool_emoji(emoji.is_unicode_emoji())}",
            f"**URL:** {hyperlink(emoji.url)}",
        ]
        return discord.Embed(
            title=f"Emoji: {emoji.name}",
            description="\n".join(emoji_info),
            color=discord.Color.blurple(),
        ).set_thumbnail(url=emoji.url)

    def get_emoji_info(self, emoji: discord.Emoji | discord.PartialEmoji) -> dict[str, discord.Embed]:
        if isinstance(emoji, discord.PartialEmoji):
            return {"Overview": self.get_partial_emoji_info(emoji)}

        emoji_info = [
            f"**ID:** `{emoji.id}`",
            f"**Name:** `{emoji.name}`",
            f"**Guild:** {emoji.guild.name if emoji.guild else emoji.guild_id}",
            f"**Is animated?** {get_bool_emoji(emoji.animated)}",
            f"**Is managed?** {get_bool_emoji(emoji.managed)}",
            f"**Is available?** {get_bool_emoji(emoji.available)}",
            f"**Requires colons?** {get_bool_emoji(emoji.require_colons)}",
            f"**Role exclusive?** {get_bool_emoji(len(emoji.roles))}",
            f"**Created:** {discord.utils.format_dt(emoji.created_at, 'R')}",
            f"**Creator:** {emoji.user.mention if emoji.user else 'Unknown'}",
            f"**URL:** {hyperlink(emoji.url)}",
        ]
        emoji_embed = discord.Embed(
            title=f"Emoji: {emoji.name}",
            description="\n".join(emoji_info),
            color=discord.Color.blurple(),
        ).set_thumbnail(url=emoji.url)

        if emoji.roles:
            emoji_roles_embed = discord.Embed(
                title=f"Roles that can use {emoji.name}:",
                description="\n".join(role.mention for role in emoji.roles[:50]),
                color=discord.Color.blurple(),
            )
            if len(emoji.roles) > 50:
                emoji_roles_embed.description += f"\n\n*... and {len(emoji.roles) - 50:,} more*"
            return {"Overview": emoji_embed, "Allowed roles": emoji_roles_embed}
        return {"Overview": emoji_embed}

    @commands.slash_command(name="emoji-info", description="Get information about an emoji.")
    async def emoji_info(self, ctx: discord.ApplicationContext, emoji: str):
        """Get information about an emoji."""
        await ctx.defer(ephemeral=True)
        try:
            emoji: discord.Emoji = await commands.EmojiConverter().convert(ctx, emoji)
        except commands.errors.BadArgument:
            try:
                emoji: discord.PartialEmoji = await commands.PartialEmojiConverter().convert(ctx, emoji)
            except commands.errors.BadArgument:
                c = self.bot.get_application_command("character-info")
                return await ctx.respond(
                    f"Emoji not found. Try </{c.name}:{c.id}> if you wanted to get information on a regular character."
                )

        embeds = self.get_emoji_info(emoji)
        view = GenericLabelledEmbedView(ctx, **embeds)
        embed = embeds["Overview"]
        button = EmojiStealButton(emoji)
        if ctx.guild and len(ctx.guild.emojis) < ctx.guild.emoji_limit:
            if ctx.user.guild_permissions.manage_emojis and ctx.me.guild_permissions.manage_emojis:
                if isinstance(emoji, discord.Emoji) or emoji.is_custom_emoji():
                    if discord.utils.get(ctx.guild.emojis, name=emoji.name) is None:
                        view.add_item(button)
                        embed.set_footer(text="Click/tap 'Steal' to add this emoji to this server.")
                if isinstance(emoji, discord.Emoji) and emoji.guild == ctx.guild:
                    view.remove_item(button)
                    embed.remove_footer()
        await ctx.respond(embed=embed, view=view)


def setup(bot):
    bot.add_cog(EmojiInfoCog(bot))
