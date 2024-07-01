import io
import logging

import discord
from discord.ext import bridge, commands
from spanner.cogs.user_info import UserInfo
from spanner.share.utils import get_log_channel


class AvatarEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.member.avatar_change")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.avatar != after.avatar:
            try:
                before_avatar = io.BytesIO(await before.display_avatar.with_static_format("webp").read())
                before_ext = "webp" if not before.display_avatar.is_animated() else "gif"
                before_avatar_file = discord.File(before_avatar, filename=f"before_avatar.{before_ext}")
            except discord.HTTPException:
                before_avatar = None
                before_avatar_file = None
            self.log.debug("%r avatar change.", after)
            if after.guild is None or after == self.bot.user:
                return

            log_channel = await get_log_channel(self.bot, after.guild.id, "member.avatar-change")
            if log_channel is None:
                return

            after_avatar = io.BytesIO(await after.display_avatar.read())
            after_ext = "webp" if not after.display_avatar.is_animated() else "gif"
            after_avatar_file = discord.File(after_avatar, filename=f"after_avatar.{after_ext}")

            embed = discord.Embed(
                title="Member avatar changed!",
                colour=discord.Colour.blue(),
                timestamp=discord.utils.utcnow(),
            )
            if before_avatar:
                embed.add_field(name="Before", value="See thumbnail (right-hand side)", inline=True)
                embed.set_thumbnail(url=f"attachment://{before_avatar_file.filename}")
            else:
                embed.add_field(name="Before", value="Could not download avatar in time.", inline=True)
            embed.add_field(name="After", value=f"[See image (below)]({after.display_avatar.url})", inline=True)

            embed.set_image(url=after.display_avatar.url)
            files = [before_avatar_file, after_avatar_file]
            files = list(filter(None, files))
            cog = UserInfo(self.bot)
            user_info_embed = (await cog.get_member_info(after))["Overview"]
            await log_channel.send(embeds=[embed, user_info_embed], files=files)


def setup(bot: bridge.Bot):
    bot.add_cog(AvatarEvents(bot))
