import asyncio

import discord
import uvicorn
from discord.ext import bridge, commands
from share.config import load_config
from tortoise import Tortoise


class CustomBridgeBot(bridge.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.web: asyncio.Task | None = None

    async def close(self) -> None:
        if self.web is not None:
            self.web.cancel()
            try:
                await self.web
            except asyncio.CancelledError:
                pass
        await super().close()

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        from api import app

        await Tortoise.init(
            db_url=load_config()["database"]["uri"],
            modules={"models": ["spanner.share.database"]},
        )
        await Tortoise.generate_schemas()
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=1237,
            forwarded_allow_ips=load_config()["web"].get("forwarded_allow_ips", "*")
        )
        config.setup_event_loop()
        server = uvicorn.Server(config)
        self.web = asyncio.create_task(server.serve())
        try:
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
