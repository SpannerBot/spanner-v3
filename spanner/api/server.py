import contextlib
import logging
import os
import time
import asyncio
from typing import Awaitable, Callable
from urllib.parse import urlparse

import fastapi
from bot import bot
from fastapi import HTTPException, Request, Response, status
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse as JSONResponse
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import RegisterTortoise

from spanner.share.config import load_config
from spanner.share.version import __sha__

from .routes import guilds_api, oauth_api
from .vars import CLIENT_SECRET, HOST_DATA, PROCESS_EPOCH

__all__ = (
    "app"
)


TORTOISE_ORM = {
    "connections": {"default": load_config()["database"]["uri"]},
    "apps": {
        "models": {
            "models": ["spanner.share.database"],
            "default_connection": "default",
        },
    },
}


def _get_root_path():
    base_url = load_config()["web"].get("base_url", "http://localhost:1234/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid base URL scheme.")
    if not parsed.netloc:
        raise ValueError("Invalid base URL netloc.")
    path = parsed.path.rstrip("/") or ""
    return path


@contextlib.asynccontextmanager
async def lifespan(_app: fastapi.FastAPI):
    async with RegisterTortoise(_app, TORTOISE_ORM, generate_schemas=True, add_exception_handlers=True):
        task = asyncio.create_task(bot.start(load_config()["spanner"]["token"]))
        try:
            yield
        finally:
            await bot.close()
            await task


log = logging.getLogger("spanner.api")
log.info("Base path is set to %r", _get_root_path())

app = fastapi.FastAPI(debug=True, lifespan=lifespan, root_path=_get_root_path(), default_response_class=JSONResponse)
app.include_router(guilds_api)
app.include_router(oauth_api)
app.mount("/assets", StaticFiles(directory="./assets", html=True), name="assets")
ratelimits = {}

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=9)


@app.middleware("http")
async def is_ready_middleware(req: Request, call_next: Callable[[Request], Awaitable[Response]]):
    if not req.url.path.startswith("/api"):
        res = await call_next(req)
        res.headers["X-Spanner-Version"] = __sha__
        # Just pass it through, skip processing
        return res

    n = time.time()
    if not bot.is_ready():
        await bot.wait_until_ready()

    ratelimits.setdefault(req.client.host, {"expires": time.time(), "hits": 0})
    rc = ratelimits[req.client.host]
    _ignore = ("/healthz", "/docs", "/redoc", "/openapi.json")
    if req.url.path not in _ignore:
        if rc["hits"] > 70:
            if rc["expires"] < n:
                rc["expires"] = n + 60
                rc["hits"] = 1
            else:
                return JSONResponse(
                    {
                        "detail": "You are being rate-limited. Please slow down your requests.",
                    },
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    {
                        "Retry-After": str(round(rc["expires"] - n)),
                        "X-Ratelimit-Remaining": "0",
                        "X-Ratelimit-Reset": str(round(rc["expires"])),
                        "X-Ratelimit-Reset-After": str(round(rc["expires"] - n)),
                    },
                )
        else:
            rc["hits"] += 1
    rl_headers = {
        "X-Ratelimit-Remaining": str(70 - rc["hits"]),
        "X-Ratelimit-Reset": str(round(rc["expires"])),
        "X-Ratelimit-Reset-After": str(round(rc["expires"] - n)),
    }
    res = await call_next(req)
    res.headers["X-Spanner-Version"] = __sha__
    res.headers.update(rl_headers)
    return res


@app.get("/healthz")
def health_check():
    if not bot.is_ready():
        # noinspection PyProtectedMember
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Bot is not online and ready yet.",
            {"Retry-After": str(round(max(2.0, bot.ws._rate_limiter.get_delay())))},
        )

    data = {
        "online": True,
        "uptime": round(time.time() - PROCESS_EPOCH),
        "latency": round(bot.latency * 1000, 2),
        "stats": {"users": len(bot.users), "guilds": len(bot.guilds), "cached_messages": len(bot.cached_messages)},
        "host": HOST_DATA,
        "warnings": [],
    }
    if not CLIENT_SECRET:
        data["warnings"].append({"detail": "CLIENT_SECRET is not set."})
    return data


if os.path.exists("./docs"):
    app.mount("/", StaticFiles(directory="./assets/docs", html=True), name="docs")
else:
    pwd = os.getcwd()
    log.warning(f"Docs have not been built - run `mkdocs build -d {pwd}/assets/docs` to generate them.")
