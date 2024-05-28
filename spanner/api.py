import logging
from urllib.parse import urlparse

import fastapi
from fastapi import HTTPException
from bot import bot
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from spanner.share.config import load_config
from spanner.share.database import GuildAuditLogEntry


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
app.mount("/assets", StaticFiles(directory="assets", html=True), name="assets")
templates = Jinja2Templates(directory="assets")

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=9)


@app.middleware("http")
async def is_ready_middleware(req, call_next):
    if not bot.is_ready():
        await bot.wait_until_ready()
    return await call_next(req)


@app.get("/guilds/{guild_id}/audit-logs")
async def get_audit_logs(req: fastapi.Request, guild_id: int):
    audit_log = await GuildAuditLogEntry.filter(guild_id=guild_id).order_by("-created_at").all()
    if not audit_log:
        raise HTTPException(404, "No audit logs found.")
    for entry in audit_log:
        await entry.fetch_related("guild")
    return templates.TemplateResponse(
        req, "guild-audit-log.html", {"guild": bot.get_guild(guild_id), "events": audit_log}
    )
