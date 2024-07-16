import asyncio
import signal
import sys

sys.path.extend([".", ".."])

import logging

import discord
import uvicorn
from discord.ext import bridge, commands
from tortoise import Tortoise
from tortoise.contrib.fastapi import RegisterTortoise

from spanner.share.config import load_config
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
                self.web = asyncio.create_task(self.web_server.serve())
                await super().start(token, reconnect=reconnect)
            finally:
                await Tortoise.close_connections()


bot = CustomBridgeBot(
    command_prefix=commands.when_mentioned_or("s!", "S!"),
    strip_after_prefix=True,
    case_insensitive=True,
    debug_guilds=load_config()["spanner"].get("debug_guilds", None),
    intents=discord.Intents.all(),
    status=discord.Status.idle,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
)
