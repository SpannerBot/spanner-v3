import logging

import discord
from discord.ext import bridge, commands

from spanner.share.utils import get_log_channel


class InviteEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.invite_events")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        log_channel = await get_log_channel(self.bot, invite.guild.id, "server.invite.create")
        if log_channel is None:
            return

        cog = self.bot.get_cog("InviteInfo")
        invite_info_embeds = await cog.get_discord_invite_info(invite)  # type: ignore
        invite_info_embeds["Overview"].title = "Invite created: " + invite.code
        invite_info_embeds["Overview"].colour = discord.Colour.green()
        await log_channel.send(embeds=list(invite_info_embeds.values()))

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        log_channel = await get_log_channel(self.bot, invite.guild.id, "server.invite.delete")
        if log_channel is None:
            return

        cog = self.bot.get_cog("InviteInfo")
        invite_info_embeds = await cog.get_discord_invite_info(invite)  # type: ignore
        invite_info_embeds["Overview"].title = "Invite deleted: " + invite.code
        invite_info_embeds["Overview"].colour = discord.Colour.red()
        await log_channel.send(embeds=list(invite_info_embeds.values()))


def setup(bot):
    bot.add_cog(InviteEvents(bot))
