import asyncio
import sys
import time


sys.path.extend([".", ".."])

import logging

import discord
import uvicorn
from discord.ext import bridge, commands
from tortoise import Tortoise
from tortoise.contrib.fastapi import RegisterTortoise

from spanner.share.config import load_config
from spanner.share.database import GuildConfig
from spanner.share.views.self_roles import PersistentSelfRoleView

TORTOISE_ORM = {
    "connections": {"default": load_config()["database"]["uri"]},
    "apps": {
        "models": {
            "models": ["spanner.share.database"],
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

        super().__init__(*args, **kwargs)

    async def close(self) -> None:
        if self.web is not None:
            self.web_server.should_exit = True
            self.web_server.force_exit = True
            self.web.cancel()
            try:
                await self.web
            except asyncio.CancelledError:
                pass
        await super().close()

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
