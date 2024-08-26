import asyncio
import copy
import os
from typing import Any, Awaitable, Callable

import discord
from discord.ext import commands

from spanner.cogs.channel_info import ChannelInfoCog
from spanner.cogs.server_info import ServerInfoCog
from spanner.share.data import verification_levels
from spanner.share.utils import get_bool_emoji
from spanner.share.views import GenericLabelledEmbedView


class ViewInfoButton(discord.ui.Button):
    def __init__(
        self,
        context: discord.ApplicationContext,
        callback: Callable[[discord.ApplicationContext, discord.Interaction], Awaitable[Any]],
        **kwargs,
    ):
        self._callback = callback
        self.one_time = kwargs.pop("one_time", True)
        self.ctx = copy.copy(context)
        kwargs["custom_id"] = os.urandom(3).hex()
        super().__init__(style=discord.ButtonStyle.blurple, **kwargs)
        self.lock = asyncio.Lock()

    async def callback(self, interaction: discord.Interaction):
        async with self.lock:
            try:
                await self._callback(self.ctx, interaction)
            finally:
                self.disabled = True
                await interaction.edit_original_response(view=self.view)


class InviteInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def get_discord_invite_info(invite: discord.Invite) -> dict[str, discord.Embed]:
        approx_member_count = invite.approximate_member_count
        approx_presence_count = invite.approximate_presence_count
        expires_at = invite.expires_at
        me = getattr(invite.guild, "me", None)

        if isinstance(invite.channel, discord.abc.GuildChannel):
            if me and invite.channel.permissions_for(invite.channel.guild.me).manage_guild:
                invite: discord.Invite = discord.utils.get(await invite.channel.guild.invites(), id=invite.id) or invite
            elif me and invite.channel.guild.me.guild_permissions.manage_guild:
                invite: discord.Invite = discord.utils.get(await invite.channel.guild.invites(), id=invite.id) or invite

        invite_lines = [
            f"**ID:** `{invite.id}`",
            f"**Code:** `{invite.code}`",
            f"**Full URL:** {invite.url}",
            f"**Creator:** {invite.inviter.mention if invite.inviter else 'Unknown'}",
            f"**Revoked?** {get_bool_emoji(invite.revoked)}",
        ]
        if invite.temporary is not None:
            invite_lines.append(f"**Grants temporary membership?** {get_bool_emoji(invite.temporary)}")
        if invite.created_at:
            invite_lines.append(f"**Created:** {discord.utils.format_dt(invite.created_at, 'R')}")
        if expires_at:
            invite_lines.append(f"**Expires:** {discord.utils.format_dt(expires_at, 'R')}")

        if approx_member_count:
            invite_lines.append(f"**Approximate member count:** {approx_member_count:,}")
        if approx_presence_count:
            invite_lines.append(f"**Approximate online count:** {approx_presence_count:,}")

        if invite.max_uses is not None:
            invite_lines.append("")
            invite_lines.append(f"**Uses:** {invite.uses:,}/{invite.max_uses or float('inf'):,}")

        invite_embed = discord.Embed(
            title=f"Invite Information - {invite.code}",
            description="\n".join(invite_lines),
            color=discord.Color.blurple(),
            url=invite.url,
        )
        result = {"Overview": invite_embed}

        if invite.scheduled_event:
            event = invite.scheduled_event
            event_text = [
                f"**ID:** `{event.id}`",
                f"**Name:** {event.name!r}",
                f"**Guild:** {event.guild.name!r}",
                f"**Creator:** {event.creator.mention if event.creator else 'Unknown'}",
                f"**Start time:** {discord.utils.format_dt(event.start_time or discord.utils.utcnow(), 'R')}",
                f"**End time:** {discord.utils.format_dt(event.end_time or discord.utils.utcnow(), 'R')}",
                f"**Subscribers:** {event.subscriber_count or 0:,}",
                f"**Interested:** {event.interested or 0:,}",
            ]
            event_embed = discord.Embed(
                title=f"Event Information - {event.name}",
                description="\n".join(event_text),
                color=discord.Color.blurple(),
                url=invite.url,
            )
            result["Event"] = event_embed

        destination_text = []
        if isinstance(invite.guild, (discord.Guild, discord.PartialInviteGuild)):
            destination_text += [
                f"**Server ID:** `{invite.guild.id}`",
                f"**Server name:** {invite.guild.name!r}",
                f"**Server verification level:** {invite.guild.verification_level.name} "
                f"({verification_levels[invite.guild.verification_level]})",
            ]
        if isinstance(invite.channel, (discord.abc.GuildChannel, discord.PartialInviteChannel)):
            destination_text += [
                f"**Channel ID:** `{invite.channel.id}`",
                f"**Channel name:** {invite.channel.name!r}",
                f"**Channel type:** {invite.channel.type.name.replace('_', ' ').title()}",
                f"**Channel created:** {discord.utils.format_dt(invite.channel.created_at, 'R')}",
            ]
        if destination_text:
            destination_embed = discord.Embed(
                title="Destination Information", description="\n".join(destination_text), color=discord.Color.blurple()
            )
            result["Destination"] = destination_embed

        return result

    @staticmethod
    def ii_guild_callback(original_view: GenericLabelledEmbedView, guild: discord.Guild):
        async def inner(ctx: discord.ApplicationContext, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            data = await ServerInfoCog.get_server_info(guild)
            embeds = {}
            for key, value in data.items():
                value = [x for x in value if x]
                if not value:
                    continue
                embed = discord.Embed(title=key.replace("_", " ").title(), color=discord.Color.blurple())
                embed.description = "\n".join(value)
                embeds[key.split("_")[0].title()] = embed

            if ctx.guild.icon:
                embeds["Overview"].set_thumbnail(url=ctx.guild.icon.url)
                embeds["Icon (Enlarged)"] = discord.Embed().set_image(url=ctx.guild.icon.with_size(4096).url)
            if ctx.guild.banner:
                embeds["Overview"].set_image(url=ctx.guild.banner.url)

            new_view = GenericLabelledEmbedView(ctx, **embeds)
            btn = discord.ui.Button(label="Back", emoji="\U000025c0\U0000fe0f", custom_id="back")

            async def _callback(i: discord.Interaction):
                await i.response.defer(invisible=True)
                btn.view.stop()

            btn.callback = _callback
            new_view.add_item(btn)
            await interaction.edit_original_response(embed=new_view.current_embed, view=new_view)
            await new_view.wait()
            await interaction.edit_original_response(embed=original_view.embeds["Overview"], view=original_view)

        return inner

    def ii_channel_callback(self, original_view: GenericLabelledEmbedView, channel: discord.abc.GuildChannel):
        async def inner(ctx: discord.ApplicationContext, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            embeds = await ChannelInfoCog(self.bot).get_channel_info(channel)

            new_view = GenericLabelledEmbedView(ctx, **embeds)
            btn = discord.ui.Button(label="Back", emoji="\U000025c0\U0000fe0f", custom_id="back")

            async def _callback(i: discord.Interaction):
                await i.response.defer(invisible=True)
                btn.view.stop()

            btn.callback = _callback
            new_view.add_item(btn)
            await interaction.edit_original_response(embed=new_view.current_embed, view=new_view)
            await new_view.wait()
            await interaction.edit_original_response(embed=original_view.embeds["Overview"], view=original_view)

        return inner

    @commands.slash_command(
        name="invite-info",
        integration_types={discord.IntegrationType.guild_install, discord.IntegrationType.user_install},
    )
    async def invite_info(self, ctx: discord.ApplicationContext, url: str):
        """Get information about an invite."""
        await ctx.defer(ephemeral=True)
        try:
            invite = await commands.InviteConverter().convert(ctx, url)
        except commands.BadInviteArgument:
            return await ctx.respond("Invalid invite.", ephemeral=True)

        embeds = await self.get_discord_invite_info(invite)
        view = GenericLabelledEmbedView(ctx, **embeds)

        _guild = self.bot.get_guild(invite.guild.id)
        if _guild:
            btn = ViewInfoButton(
                ctx, self.ii_guild_callback(view, _guild), label="View Server Info", style=discord.ButtonStyle.secondary
            )
            view.add_item(btn)
        _channel = discord.utils.get(set(self.bot.get_all_channels()), id=invite.channel.id)
        if _channel:
            btn = ViewInfoButton(
                ctx,
                self.ii_channel_callback(view, _channel),
                label="View Channel Info",
                style=discord.ButtonStyle.secondary,
            )
            view.add_item(btn)
        if not ctx.interaction.authorizing_integration_owners.guild_id:
            for embed in embeds.values():
                embed.set_footer(text="This information may be incomplete as I am not in the server.")
        await ctx.respond(embed=embeds["Overview"], view=view, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(InviteInfo(bot))
