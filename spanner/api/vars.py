import logging
import os
import platform

import psutil

from spanner.share.config import load_config

__all__ = (
    "HOST_DATA",
    "PROCESS_EPOCH",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_SECONDS",
    "OAUTH_URL",
    "CLIENT_SECRET",
)

log = logging.getLogger("spanner.api.vars")

HOST_DATA = {
    "architecture": platform.machine(),
    "platform": platform.platform(terse=True),
    "python": platform.python_version(),
    "system": {"name": platform.system(), "version": platform.version()},
    "docker": os.path.exists("/.dockerenv"),
    "cpus": os.cpu_count(),
}
PROCESS_EPOCH = psutil.Process(os.getpid()).create_time()
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
