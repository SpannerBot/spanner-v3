import datetime
import logging
import os
import platform
import secrets
import time
from typing import Annotated, Awaitable, Callable
from urllib.parse import urlparse

import aiohttp
import discord.utils
import fastapi
import jwt
import psutil
from bot import bot
from fastapi import Cookie, Depends, HTTPException, Header, Request, Response, status
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from spanner.share.config import load_config
from spanner.share.database import DiscordOauthUser, GuildAuditLogEntry, GuildAuditLogEntryPydantic
from spanner.share.version import __sha__


def _get_root_path():
    base_url = load_config()["web"].get("base_url", "http://localhost:1234/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid base URL scheme.")
    if not parsed.netloc:
        raise ValueError("Invalid base URL netloc.")
    path = parsed.path.rstrip("/") or ""
    return path


HOST_DATA = {
    "architecture": platform.machine(),
    "platform": platform.platform(terse=True),
    "python": platform.python_version(),
    "system": {"name": platform.system(), "version": platform.version()},
    "docker": os.path.exists("/.dockerenv"),
    "cpus": os.cpu_count(),
}
PROCESS_EPOCH = psutil.Process(os.getpid()).create_time()


log = logging.getLogger("spanner.api")
log.info("Base path is set to %r", _get_root_path())

app = fastapi.FastAPI(debug=True, root_path=_get_root_path())
app.mount("/assets", StaticFiles(directory="./assets", html=True), name="assets")
templates = Jinja2Templates(directory="assets")

authorise_sessions = {}
ratelimits = {}

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=9)

_DEFAULT_JWT = "2f7c204ac7d45f684aae0647745a4d2f986037ccb2e60d5b3c95f2690728821c"
SECRET_KEY = (
    os.getenv(
        "JWT_SECRET_KEY",
        load_config()["web"].get("jwt_secret_key", ""),
    )
    or _DEFAULT_JWT
)
if SECRET_KEY == _DEFAULT_JWT:
    log.critical("Using default JWT secret key. change it! set $JWT_SECRET_KEY or set config.toml[web.jwt_secret_key]")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 806400  # 1 week, same length as discord token
OAUTH_URL = (
    "https://discord.com/oauth2/authorize?"
    "client_id={client_id}"
    "&response_type=code"
    "&redirect_uri={redirect_uri}"
    "&scope=identify+guilds"
    "&state={state}"
)
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", load_config()["web"].get("discord_client_secret"))
if not CLIENT_SECRET:
    log.critical(
        "No client secret passed to API (either $DISCORD_CLIENT_SECRET or config.toml[web.discord_client_secret])."
        " Authorised endpoints will be unavailable."
    )


async def logged_in_user(req: Request, token: str = Cookie(None), x_session: str = Header(None, alias="X-Session")):
    url = req.url_for("discord_authorise")
    url.include_query_params(from_url=req.url.path)
    reauth = HTTPException(status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": str(url)})
    token = token or x_session
    if not token:
        reauth.detail = "Please log in with discord: %s" % str(url)
        raise reauth

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = await DiscordOauthUser.get_or_none(id=int(payload["sub"]))
        if not user:
            raise HTTPException(404, "User not found.")
        return user
    except jwt.ExpiredSignatureError:
        reauth.detail = "Token expired. %s" % str(url)
        raise reauth
    except jwt.InvalidTokenError:
        reauth.detail = "Invalid token. %s" % str(url)
        raise reauth


@app.middleware("http")
async def is_ready_middleware(req: Request, call_next: Callable[[Request], Awaitable[Response]]):
    if req.url.path == "/healthz":
        res = await call_next(req)
        res.headers["X-Spanner-Version"] = __sha__
        # Just pass it through, skip processing
        return res
    n = time.time()
    if not bot.is_ready():
        await bot.wait_until_ready()

    ratelimits[req.client.host].setdefault({"expires": time.time(), "hits": 0})
    rc = ratelimits[req.client.host]
    _ignore = ("/healthz", "/docs", "/redoc", "/openapi.json")
    if req.url.path not in _ignore:
        if rc["hits"] > 70:
            if rc["expires"] < time.time():
                rc["expires"] = time.time() + 60
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


@app.get("/oauth/callback/discord")
async def discord_authorise(req: Request, code: str = None, state: str = None, from_url: str = None):
    if not bot.is_ready() or not CLIENT_SECRET:
        raise HTTPException(503, "Not ready.", {"Retry-After": "30"})
    if not all((code, state)):
        log.info(
            "Request %r had no code (%r) or state (%r) - redirecting to login from %r.",
            req,
            code,
            state,
            from_url or "/",
        )
        state_key = secrets.token_urlsafe()
        if from_url and "/oauth/callback/discord" in from_url:
            from_url = "https://discord.gg/TveBeG7"
        authorise_sessions[state_key] = from_url
        r = RedirectResponse(
            url=OAUTH_URL.format(
                client_id=bot.user.id,
                redirect_uri=str(req.base_url) + "oauth/callback/discord",
                state=state_key,
            )
            + "&prompt=none"
        )
        r.set_cookie("_state", state_key, max_age=300, httponly=True, samesite="strict")
        return r
    elif state not in authorise_sessions:
        raise HTTPException(403, "Invalid or expired request.")
    elif state != req.cookies.get("_state"):
        raise HTTPException(403, "Unable to authenticate request is legitimate.")
    to = authorise_sessions.pop(state)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(req.base_url) + "oauth/callback/discord",
        "scope": "identify guilds",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/oauth2/token", data=data, auth=aiohttp.BasicAuth(str(bot.user.id), CLIENT_SECRET)
        ) as response:
            response_data = await response.json()
            if response.status != 200:
                raise HTTPException(response.status, response_data)
            elif not all(x in response_data["scope"] for x in ("identify", "guilds")):
                log.warning(f"User authenticated with {response_data['scope']!r} scopes, not 'identify guilds'.")
                return RedirectResponse(req.url_for("discord_authorise", from_url=from_url))
        async with session.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {response_data['access_token']}"},
        ) as response:
            response_data["user"] = await response.json()
            user_data: discord.Member | None = await discord.utils.get_or_fetch(
                bot, "user", int(response_data["user"]["id"])
            )
            if not user_data:
                raise HTTPException(404, "User not found.")
            user = await DiscordOauthUser.get_or_none(id=user_data.id)
            exp = discord.utils.utcnow() + datetime.timedelta(seconds=response_data["expires_in"])
            token = jwt.encode(
                {"sub": user_data.id, "exp": exp},
                SECRET_KEY,
                algorithm=ALGORITHM,
            )
            if not user:
                user = DiscordOauthUser(
                    id=user_data.id,
                    access_token=response_data["access_token"],
                    refresh_token=response_data["refresh_token"],
                    expires_at=response_data["expires_in"],
                    session=token,
                )
            else:
                user.access_token = response_data["access_token"]
                user.refresh_token = response_data["refresh_token"]
                user.expires_at = response_data["expires_in"]
                user.session = token
            await user.save()
            if not to:
                to = f"{str(req.base_url)}?token={user.session}"
            response = RedirectResponse(url=to, status_code=303)
            response.set_cookie("_token", user.session, max_age=ACCESS_TOKEN_EXPIRE_SECONDS)
            response.delete_cookie("_state")
            return response


@app.get("/guilds/{guild_id}/audit-logs")
async def get_audit_logs(req: Request, guild_id: int, user: Annotated[DiscordOauthUser, Depends(logged_in_user)]):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(404, "Guild not found.")
    try:
        member = await guild.fetch_member(user.id)
    except discord.NotFound:
        raise HTTPException(404, f"You are not in {guild.name!r}.")
    except discord.HTTPException:
        raise HTTPException(403, "Forbidden (unable to check membership)")
    else:
        if not member.guild_permissions.view_audit_log:
            raise HTTPException(403, "Forbidden (you need 'view audit log' permissions.)")

    audit_log = await GuildAuditLogEntry.filter(guild_id=guild_id).order_by("-created_at").all()
    if not audit_log:
        raise HTTPException(404, "No audit logs found.")

    if "application/json" in req.headers.get("Accept", ""):
        return [await GuildAuditLogEntryPydantic.from_tortoise_orm(entry) for entry in audit_log]

    for entry in audit_log:
        await entry.fetch_related("guild")
    return templates.TemplateResponse(
        "guild-audit-log.html", {"request": req, "guild": bot.get_guild(guild_id), "events": audit_log}
    )
