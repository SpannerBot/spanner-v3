import asyncio
import copy
import os

import discord
from discord.ext import commands

from spanner.share.data import verification_levels
from spanner.share.utils import first_line, get_bool_emoji, humanise_bytes, hyperlink
from spanner.share.views import GenericLabelledEmbedView


class ViewInfoButton(discord.ui.Button):
    def __init__(self, context: discord.ApplicationContext, command: discord.ApplicationCommand, **kwargs):
        self.command = command
        self.one_time = kwargs.pop("one_time", True)
        self.ctx = copy.copy(context)
        kwargs["custom_id"] = os.urandom(3).hex()
        super().__init__(style=discord.ButtonStyle.blurple, **kwargs)
        self.lock = asyncio.Lock()

    async def callback(self, interaction: discord.Interaction):
        ctx = copy.copy(self.ctx)
        ctx.interaction = interaction
        async with self.lock:
            try:
                await ctx.invoke(self.command)
            finally:
                self.disabled = True
                await interaction.edit_original_response(view=self.view)


class InviteInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def get_discord_invite_info(invite: discord.Invite) -> dict[str, discord.Embed]:
        approx_member_count = invite.approximate_member_count
        approx_presence_count = invite.approximate_presence_count
        expires_at = invite.expires_at

        if isinstance(invite.channel, discord.abc.GuildChannel):
            if invite.channel.permissions_for(invite.channel.guild.me).manage_guild:
                invite: discord.Invite = discord.utils.get(
                    await invite.channel.guild.invites(),
                    id=invite.id
                ) or invite
            elif invite.channel.guild.me.guild_permissions.manage_guild:
                invite: discord.Invite = discord.utils.get(
                    await invite.channel.guild.invites(),
                    id=invite.id
                ) or invite

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
            url=invite.url
        )
        result = {
            "Overview": invite_embed
        }

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
                url=invite.url
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
                title="Destination Information",
                description="\n".join(destination_text),
                color=discord.Color.blurple()
            )
            result["Destination"] = destination_embed

        return result

    @commands.slash_command(name="invite-info")
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
            shit_ctx = copy.copy(ctx)
            shit_ctx.guild = _guild
            view.add_item(
                ViewInfoButton(
                    shit_ctx,
                    self.bot.get_application_command("server-info"),
                    label="View Server Info"
                )
            )
        _channel = discord.utils.get(set(self.bot.get_all_channels()), id=invite.channel.id)
        if _channel:
            shit_ctx = copy.copy(ctx)
            shit_ctx.channel = _channel
            view.add_item(
                ViewInfoButton(
                    shit_ctx,
                    self.bot.get_application_command("channel-info"),
                    label="View Channel Info"
                )
            )
        await ctx.respond(
            embed=embeds["Overview"],
            view=view,
            ephemeral=True
        )


def setup(bot: commands.Bot):
    bot.add_cog(InviteInfoCog(bot))
