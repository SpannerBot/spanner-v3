import collections
import logging
import os
import secrets
from typing import Annotated
from urllib.parse import urlparse

import aiohttp
import discord.utils
import fastapi
import jwt
from fastapi import HTTPException, Depends, Cookie
from bot import bot
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from spanner.share.config import load_config
from spanner.share.database import GuildAuditLogEntry, DiscordOauthUser, GuildAuditLogEntryPydantic


def _get_root_path():
    base_url = load_config()["web"].get("base_url", "http://localhost:1234/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid base URL scheme.")
    if not parsed.netloc:
        raise ValueError("Invalid base URL netloc.")
    path = parsed.path.rstrip("/") or ""
    return path


log = logging.getLogger("spanner.api")
log.info("Base path is set to %r", _get_root_path())

app = fastapi.FastAPI(debug=True, root_path=_get_root_path())
app.mount("/assets", StaticFiles(directory="./assets", html=True), name="assets")
templates = Jinja2Templates(directory="assets")

authorise_sessions = collections.deque(maxlen=10240)

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=9)

SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    load_config()["web"].get("jwt_secret_key", "2f7c204ac7d45f684aae0647745a4d2f986037ccb2e60d5b3c95f2690728821c"),
)
if SECRET_KEY == "2f7c204ac7d45f684aae0647745a4d2f986037ccb2e60d5b3c95f2690728821c":
    log.critical("Using default JWT secret key. change it! set $JWT_SECRET_KEY or set config.toml[web.jwt_secret_key]")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 806400  # 1 week, same length as discord token
OAUTH_URL = ("https://discord.com/oauth2/authorize?"
             "client_id={client_id}"
             "&response_type=code"
             "&redirect_uri={redirect_uri}"
             "&scope=identify+guilds"
             "&state={state}")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", load_config()["web"].get("discord_client_secret"))
if CLIENT_SECRET:
    log.critical(
        "No client secret passed to API (either $DISCORD_CLIENT_SECRET or config.toml[web.discord_client_secret])."
        " Authorised endpoints will be unavailable."
    )


async def logged_in_user(token: str = Cookie(None)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = await DiscordOauthUser.get_or_none(id=int(payload["sub"]))
        if not user:
            raise HTTPException(404, "User not found.")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token.")


@app.middleware("http")
async def is_ready_middleware(req, call_next):
    if not bot.is_ready():
        await bot.wait_until_ready()
    return await call_next(req)


@app.get("/oauth/callback/discord")
async def discord_authorise(req: fastapi.Request, code: str = None, state: str = None):
    if not bot.is_ready() or not CLIENT_SECRET:
        raise HTTPException(503, "Not ready.")
    if not all((code, state)):
        state_key = secrets.token_urlsafe()
        authorise_sessions.append(state_key)
        return fastapi.responses.RedirectResponse(
            url=OAUTH_URL.format(
                client_id=bot.user.id,
                redirect_uri=str(req.base_url) + "oauth/callback/discord",
                state=state_key,
            )
        )
    elif state not in authorise_sessions:
        raise HTTPException(403, "Invalid state.")
    authorise_sessions.remove(state)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(req.base_url) + "oauth/callback/discord",
        "scope": "identify guilds",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            auth=aiohttp.BasicAuth(str(bot.user.id), CLIENT_SECRET)
        ) as response:
            response_data = await response.json()
            if response.status != 200:
                raise HTTPException(response.status, response_data)
            elif response_data["scope"] != "identify guilds":
                return fastapi.responses.RedirectResponse(req.url_for("discord_authorise"))
        async with session.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {response_data['access_token']}"}
        ) as response:
            response_data["user"] = await response.json()
            user_data = await discord.utils.get_or_fetch(bot, "user", int(response_data["user"]["id"]))
            if not user_data:
                raise HTTPException(404, "User not found.")
            user = await DiscordOauthUser.get_or_none(user_id=user_data.id)
            token = jwt.encode(
                {"sub": user.id, "exp": max(ACCESS_TOKEN_EXPIRE_SECONDS, user.expires_at)},
                SECRET_KEY,
                algorithm=ALGORITHM,
            )
            if not user:
                user = await DiscordOauthUser.create(
                    id=user_data.id,
                    access_token=response_data["access_token"],
                    refresh_token=response_data["refresh_token"],
                    expires_at=response_data["expires_in"],
                    session=token.decode("utf-8"),
                )
            else:
                user.access_token = response_data["access_token"]
                user.refresh_token = response_data["refresh_token"]
                user.expires_at = response_data["expires_in"]
                user.session = token.decode("utf-8")
                await user.save()
            response = fastapi.responses.RedirectResponse(
                url=f"{str(req.base_url)}?token={user.session}",
                status_code=303
            )
            response.set_cookie("token", user.session, max_age=ACCESS_TOKEN_EXPIRE_SECONDS)
            return response


@app.get("/guilds/{guild_id}/audit-logs")
async def get_audit_logs(
        req: fastapi.Request,
        guild_id: int,
        user: Annotated[DiscordOauthUser, Depends(logged_in_user)]
):
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

    if "Mozilla" not in req.headers.get("User-Agent", ""):
        return await GuildAuditLogEntryPydantic.from_queryset(audit_log)

    for entry in audit_log:
        await entry.fetch_related("guild")
    return templates.TemplateResponse(
        "guild-audit-log.html", {"request": req, "guild": bot.get_guild(guild_id), "events": audit_log}
    )
