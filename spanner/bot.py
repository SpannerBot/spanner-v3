import asyncio
import sys
import time
from collections import deque

from tortoise.transactions import in_transaction

sys.path.extend([".", ".."])

import logging

import discord
import uvicorn
from discord.ext import bridge, commands, tasks
from tortoise import Tortoise
from tortoise.contrib.fastapi import RegisterTortoise

from spanner.share.config import load_config
from spanner.share.database import GuildConfig
from spanner.share.views.self_roles import PersistentSelfRoleView

TORTOISE_ORM = {
    "connections": {"default": load_config()["database"]["uri"]},
    "apps": {
        "models": {
            "models": ["spanner.share.database", "aerich.models"],
            "default_connection": "default",
        },
    },
}


log = logging.getLogger(__name__)


class CustomBridgeBot(bridge.Bot):
    def __init__(self, *args, **kwargs):
        self.web_server: uvicorn.Server | None = kwargs.pop("server", None)
        self.web: asyncio.Task | None = None

        _config = load_config()["spanner"]
        kwargs["debug_guilds"] = _config.get("debug_guilds", None)

        intents_config = _config.get("intents", discord.Intents.default().value)
        if isinstance(intents_config, int):
            intents = discord.Intents.default()
            intents.value = intents_config
        elif isinstance(intents_config, dict):
            intents = discord.Intents(**intents_config)
        else:
            raise ValueError("Invalid intents configuration. Must be bitfield value, or table.")
        kwargs["intents"] = intents
        self.epoch = time.time()
        self.latency_history = deque(maxlen=1440)

        super().__init__(*args, **kwargs)

    @tasks.loop(minutes=1)
    async def update_latency(self):
        seconds_util_next_full_minute = 60 - time.time() % 60
        await asyncio.sleep(seconds_util_next_full_minute)
        if not bot.is_ready():
            await bot.wait_until_ready()

        try:
            latency = round(bot.latency * 1000, 2)
        except (AttributeError, OverflowError, ZeroDivisionError):
            latency = 3600000
        latency = max(-3600000, min(3600000, latency))
        bot.latency_history.append({"timestamp_ms": int(time.time() * 1000), "latency": latency})

    async def close(self) -> None:
        if self.web is not None:
            self.web_server.should_exit = True
            self.web_server.force_exit = True
            self.web.cancel()
            try:
                await self.web
            except asyncio.CancelledError:
                pass
        self.update_latency.stop()
        await super().close()

    async def clean_old_self_role_menus(self):
        from spanner.share.database import GuildAuditLogEntry, SelfRoleMenu

        await self.wait_until_ready()
        log.info("Starting cleanup of old, invalid self role menu messages")
        async with in_transaction() as conn:
            for menu in await SelfRoleMenu.all().prefetch_related("guild"):
                menu: SelfRoleMenu
                menu_json = {
                    "id": str(menu.id),
                    "channel": menu.channel,
                    "message": menu.message,
                    "roles": menu.roles,
                    "name": menu.name,
                    "maximum": menu.maximum,
                    "mode": menu.mode,
                }
                guild = self.get_guild(menu.guild.id)
                if not guild:
                    log.warning("Cleaning up self-role menu %r - guild not found.", menu)
                    await GuildAuditLogEntry.generate(
                        menu.guild.id,
                        self.user,
                        "self-roles",
                        "remove",
                        "The guild for this menu was not found.",
                        metadata={
                            "menu": menu_json,
                        },
                        using_db=conn,
                    )
                    await menu.delete(using_db=conn)
                    continue
                channel = self.get_channel(menu.channel)
                if not channel:
                    log.warning("Cleaning up self-role menu %r - channel not found.", menu)
                    await GuildAuditLogEntry.generate(
                        menu.guild.id,
                        self.user,
                        "self-roles",
                        "remove",
                        "The channel for this menu was not found.",
                        metadata={
                            "menu": menu_json,
                        },
                        using_db=conn,
                    )
                    await menu.delete(using_db=conn)
                    continue
                try:
                    message = await channel.fetch_message(menu.message)
                except (discord.NotFound, discord.Forbidden) as e:
                    log.warning("Cleaning up self-role menu %r - message not found, or forbidden.", menu)
                    await GuildAuditLogEntry.generate(
                        menu.guild.id,
                        self.user,
                        "self-roles",
                        "remove",
                        "The message for this menu was not found, or I was forbidden from fetching it.",
                        metadata={
                            "menu": menu_json,
                            "exception": str(e),
                        },
                        using_db=conn,
                    )
                    await menu.delete(using_db=conn)
                    continue
                if not any((channel.guild.get_role(x) for x in menu.roles)):
                    log.warning("Cleaning up self-role menu %r - no more valid roles.", menu)
                    await menu.delete(using_db=conn)
                    await GuildAuditLogEntry.generate(
                        menu.guild.id,
                        self.user,
                        "self-roles",
                        "remove",
                        "All of the roles for this menu do not exist anymore. The related message was deleted.",
                        metadata={
                            "menu": menu_json,
                        },
                        using_db=conn,
                    )
                    try:
                        await message.delete(delay=0.1)
                    except discord.HTTPException:
                        pass
        log.info("Finished cleanup of old, invalid self role menu messages")

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        from spanner.share.database import SelfRoleMenu

        # noinspection PyTypeChecker
        async with RegisterTortoise(
            self.web_server.config.app, TORTOISE_ORM, generate_schemas=True, add_exception_handlers=True
        ):
            for menu in await SelfRoleMenu.all().prefetch_related("guild"):
                log.info("Adding persistent view: %r", menu)
                self.add_view(PersistentSelfRoleView(menu), message_id=menu.message)
            try:
                if load_config()["web"].get("enabled", True) is True:
                    self.web = asyncio.create_task(self.web_server.serve())
                self.epoch = time.time()
                self.update_latency.start()
                self.loop.create_task(self.clean_old_self_role_menus()).add_done_callback(
                    lambda _: log.info("Cleanup task complete")
                )
                await super().start(token, reconnect=reconnect)
            finally:
                await Tortoise.close_connections()


bot = CustomBridgeBot(
    command_prefix=commands.when_mentioned_or("s!", "S!"),
    strip_after_prefix=True,
    case_insensitive=True,
    status=discord.Status.idle,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
)


@bot.before_invoke
async def ensure_database(ctx):
    if ctx.guild is not None:
        await GuildConfig.get_or_create(guild_id=ctx.guild.id)
