import datetime
import time
import platform
from typing import Literal

from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from .routes.config import router as config_router
from .routes.discord_api import router as discord_router
from .routes.oauth2 import router as oauth2_router
from .vars import CORS_ALLOW_CREDENTIALS, CORS_ALLOW_HEADERS, CORS_ALLOW_METHODS, CORS_ALLOW_ORIGINS, ROOT_PATH

app = FastAPI(
    debug=True,
    title="Spanner API",
    version="3.0.0a1.dev1",
    root_path=ROOT_PATH
)


@app.get("", include_in_schema=False)
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


class HealthZResponse(BaseModel):
    class GuildsPart(BaseModel):
        total: int
        unavailable: list[str]
        """A list of guild IDs that are unavailable"""
    class UserPart(BaseModel):
        """All fields may be None if the bot is not ready"""
        id: str | None
        name: str | None
        avatar: str | None
        """Avatar hash if any"""
    class LatencyPart(BaseModel):
        class LatencyHistoryPart(BaseModel):
            timestamp_ms: int | float
            """Unix timestamp in milliseconds"""
            latency: float
            """Latency in milliseconds, to two decimal places."""

        now: int
        """Current latency in milliseconds"""
        history: list[LatencyHistoryPart]
        """Up to the last 1440 latencies in milliseconds"""

    status: str
    """"ok" if the bot is ready, "offline" if not"""
    online: bool
    """If the bot is online and connected to discord"""
    uptime: int
    """The number of seconds the bot has been online"""
    guilds: GuildsPart
    host: str
    """Server hostname"""
    user: UserPart
    """Bot user information"""
    latency: LatencyPart
    """Bot latency information"""


@app.get("/healthz")
async def health() -> HealthZResponse:
    """Gets the health status of the bot and API."""
    from spanner.bot import bot

    return HealthZResponse.model_validate(
        {
            "status": {True: "ok", False: "offline"}[bot.is_ready()],
            "online": bot.is_ready() and not bot.is_closed(),
            "uptime": round(time.time() - bot.epoch),
            "guilds": {
                "total": len(bot.guilds),
                "unavailable": [str(g.id) for g in bot.guilds if g.unavailable]
            },
            "host": platform.node() or "unknown",
            "user": {
                "id": str(bot.user.id) if bot.user else None,
                "name": bot.user.name if bot.user else None,
                "avatar": bot.user.avatar.key if bot.user and bot.user.avatar else None
            },
            "latency": {
                "now": round(bot.latency * 1000),
                "history": list(bot.latency_history)
            }
        }
    )

app.include_router(oauth2_router, prefix="/oauth2")
app.include_router(discord_router, prefix="/_discord")
app.include_router(config_router, prefix="/config")

if CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS or ["http://localhost:1237", "http://localhost:3000"],
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
    )
