import asyncio
import datetime
import logging
import os
import random

import discord
import httpx
from discord.ext import bridge, commands

from spanner.share.config import load_config
from spanner.share.utils import get_log_channel
from spanner.share.database import GuildNickNameModeration


class NicknameChangeEvents(commands.Cog):
    def __init__(self, bot: bridge.Bot):
        self.bot = bot
        self.log = logging.getLogger("spanner.events.nickname_change")
        self.moderation_lock = asyncio.Lock()

    async def wait_for_audit_log(self, guild: discord.Guild, target: discord.Member, nick: str | None):
        await asyncio.sleep(1)

        def the_check(e: discord.AuditLogEntry):
            if e.target == target and e.action == discord.AuditLogAction.member_update:
                return entry.target.nick == nick

        if not guild.me.guild_permissions.view_audit_log:
            return
        now = discord.utils.utcnow()
        after = now - datetime.timedelta(seconds=59)
        async for entry in guild.audit_logs(after=after, action=discord.AuditLogAction.member_update):
            if the_check(entry):
                return entry

        try:
            entry = await self.bot.wait_for("audit_log_entry", check=the_check, timeout=600)
            if not entry:
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            self.log.debug(
                "Event(guild=%r, target=%r): Timeout waiting for audit log entry. Likely not a nick change.",
                guild,
                target,
            )
        else:
            return entry

    async def moderate_name(self, after: discord.Member):
        openai_token = os.getenv("OPENAI_API_KEY", load_config()["spanner"].get("openai_token"))
        if not openai_token:
            return False
        moderation = await GuildNickNameModeration.get_or_none(
            guild_id=after.guild.id
        )
        if moderation is None:
            return False
        log_channel = await get_log_channel(self.bot, after.guild.id, "member.nickname-change")
        if not log_channel:
            return
        if any(getattr(moderation, x) is True for x in GuildNickNameModeration.CATEGORIES.keys()):
            async with httpx.AsyncClient() as client:
                async with self.moderation_lock:
                    odn = after.display_name
                    response = await client.post(
                        "https://api.openai.com/v1/moderations",
                        json={
                            "model": "text-moderation-stable",
                            "input": odn
                        },
                        headers={"Authorization": f"Bearer {openai_token}"}
                    )
                response.raise_for_status()
                data = response.json()["results"][0]
                self.log.info("OpenAI moderation response: %r", data)
                flagged = data["flagged"]
                data = data["categories"]
                data["hate"] = data["hate"] or data["hate/threatening"]
                data["sexual"] = data["sexual"] or data["sexual/minors"]
                data["violence"] = data["violence"] or data["violence/graphic"]
                data["self-harm"] = data["self-harm"] or data["self-harm/intent"] or data["self-harm/instructions"]
                data["harassment"] = data["harassment"] or data["harassment/threatening"]

                if flagged is False:
                    return False

                if after.nick is None:
                    with open("/usr/share/dict/words") as words_file:
                        words = tuple(set(map(str.casefold, words_file.readlines())))
                    new_name = [random.choice(words), random.choice(words)]
                    new_name = "-".join(new_name) + str(random.randint(0, 20))
                    new_name = new_name[:32]
                else:
                    new_name = None

                try:
                    if data["sexual"] and moderation.sexual:
                        await after.edit(
                            nick=new_name,
                            reason=f"Nickname ({after.display_name}) contains sexual content, which this server has "
                                   f"enabled filtering of."
                        )
                        await log_channel.send(
                            embed=discord.Embed(
                                title="Member nickname filtered: sexual content",
                                description=f"{after.mention}'s nickname was filtered due to sexual content.\n"
                                            f"Was: {odn}\n"
                                            f"Now: {new_name}",
                                colour=discord.Colour.red(),
                                timestamp=discord.utils.utcnow()
                            ).set_thumbnail(url=after.display_avatar.url).set_author(
                                name=after.guild.me.display_name,
                                icon_url=after.guild.me.display_avatar.url
                            )
                        )
                    elif data["hate"] and moderation.hate:
                        await after.edit(
                            nick=new_name,
                            reason=f"Nickname ({after.display_name}) contains hate speech, which this server has "
                                   f"enabled filtering of."
                        )
                        await log_channel.send(
                            embed=discord.Embed(
                                title="Member nickname filtered: hate speech",
                                description=f"{after.mention}'s nickname was filtered due to hate speech.\n"
                                            f"Was: {odn}\n"
                                            f"Now: {new_name}",
                                colour=discord.Colour.red(),
                                timestamp=discord.utils.utcnow()
                            ).set_thumbnail(url=after.display_avatar.url).set_author(
                                name=after.guild.me.display_name,
                                icon_url=after.guild.me.display_avatar.url
                            )
                        )
                    elif data["harassment"] and moderation.harassment:
                        await after.edit(
                            nick=new_name,
                            reason=f"Nickname ({after.display_name}) contains harassment, which this server has "
                                   f"enabled filtering of."
                        )
                        await log_channel.send(
                            embed=discord.Embed(
                                title="Member nickname filtered: harassment",
                                description=f"{after.mention}'s nickname was filtered due to harassment.\n"
                                            f"Was: {odn}\n"
                                            f"Now: {new_name}",
                                colour=discord.Colour.red(),
                                timestamp=discord.utils.utcnow()
                            ).set_thumbnail(url=after.display_avatar.url).set_author(
                                name=after.guild.me.display_name,
                                icon_url=after.guild.me.display_avatar.url
                            )
                        )
                    elif data["self-harm"] and moderation.self_harm:
                        await after.edit(
                            nick=new_name,
                            reason=f"Nickname ({after.display_name}) contains self-harm content, which this server has "
                                   f"enabled filtering of."
                        )
                        await log_channel.send(
                            embed=discord.Embed(
                                title="Member nickname filtered: self-harm",
                                description=f"{after.mention}'s nickname was filtered due to self-harm.\n"
                                            f"Was: {odn}\n"
                                            f"Now: {new_name}",
                                colour=discord.Colour.red(),
                                timestamp=discord.utils.utcnow()
                            ).set_thumbnail(url=after.display_avatar.url).set_author(
                                name=after.guild.me.display_name,
                                icon_url=after.guild.me.display_avatar.url
                            )
                        )
                    elif data["violence"] and moderation.violence:
                        await after.edit(
                            nick=new_name,
                            reason=f"Nickname ({after.display_name}) contains violence, which this server has "
                                   f"enabled filtering of."
                        )
                        await log_channel.send(
                            embed=discord.Embed(
                                title="Member nickname filtered: violence",
                                description=f"{after.mention}'s nickname was filtered due to violence.\n"
                                            f"Was: {odn}\n"
                                            f"Now: {new_name}",
                                colour=discord.Colour.red(),
                                timestamp=discord.utils.utcnow()
                            ).set_thumbnail(url=after.display_avatar.url).set_author(
                                name=after.guild.me.display_name,
                                icon_url=after.guild.me.display_avatar.url
                            )
                        )
                except discord.Forbidden as e:
                    if log_channel is not None:
                        await log_channel.send(
                            f"Failed to moderate {after}'s nickname after it was flagged. Reason: `{e}`\n"
                            f"A moderator will need to change it manually,"
                        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        self.log.debug("%r update %r -> %r.", before, before.guild, after)
        if before.guild is None or before == self.bot.user:
            return

        log_channel = await get_log_channel(self.bot, before.guild.id, "member.nickname-change")
        if log_channel is None:
            return

        if before.display_name != after.display_name:
            embed = discord.Embed(
                title="Member changed nickname!",
                colour=discord.Colour.blue(),
                description=f"* Before: {discord.utils.escape_markdown(before.display_name or 'N/A')}\n"
                f"* After: {discord.utils.escape_markdown(after.display_name or 'N/A')}\n",
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            msg = await log_channel.send(embed=embed)
            entry = await self.wait_for_audit_log(before.guild, after, after.display_name)
            if entry:
                embed.set_author(name=f"Moderator: {entry.user}", icon_url=entry.user.display_avatar.url)
                if entry.reason:
                    embed.add_field(name="Reason", value=entry.reason, inline=False)
                embed.set_footer(text="Nickname change details fetched from audit log.")
                await msg.edit(embed=embed)
            await self.moderate_name(after)


def setup(bot: bridge.Bot):
    bot.add_cog(NicknameChangeEvents(bot))
