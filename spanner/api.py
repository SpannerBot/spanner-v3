import collections
import logging
import os
import secrets
from urllib.parse import urlparse

import fastapi
import jwt
from fastapi import HTTPException, Depends, Security
from bot import bot
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from spanner.share.config import load_config
from spanner.share.database import GuildAuditLogEntry, DiscordOauthUser


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
        "client_id": bot.user.id,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(req.base_url) + "oauth/callback/discord",
        "scope": "identify guilds",
    }


@app.get("/guilds/{guild_id}/audit-logs")
async def get_audit_logs(req: fastapi.Request, guild_id: int):
    audit_log = await GuildAuditLogEntry.filter(guild_id=guild_id).order_by("-created_at").all()
    if not audit_log:
        raise HTTPException(404, "No audit logs found.")
    for entry in audit_log:
        await entry.fetch_related("guild")
    return templates.TemplateResponse(
        "guild-audit-log.html", {"request": req, "guild": bot.get_guild(guild_id), "events": audit_log}
    )
