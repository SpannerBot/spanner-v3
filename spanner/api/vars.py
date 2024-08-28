import hashlib
import os
import platform
from typing import Any, Callable

from spanner.share.config import load_config


def _get_item(_from: dict, name: str, default: Any = None, cast: Callable = None) -> Any:
    cast = cast or (lambda x: x)
    return cast(os.getenv(name.upper(), _from.get(name, default)))


CONFIG: dict = load_config()
BOT_TOKEN: str = _get_item(CONFIG["spanner"], "token", None, str)
WEB_CONFIG: dict = load_config()["web"]
WEB_CONFIG.setdefault("cors", {})
CORS_CONFIG = WEB_CONFIG["cors"]


HOST = _get_item(WEB_CONFIG, "host", "127.0.0.1", str)
PORT = _get_item(WEB_CONFIG, "port", 1237, int)
BASE_URL = _get_item(WEB_CONFIG, "base_url", f"http://{HOST}:{PORT}", str)
ROOT_PATH: str | None = _get_item(WEB_CONFIG, "root_path", None)
JWT_SECRET_KEY = _get_item(WEB_CONFIG, "jwt_secret_key", hashlib.sha256(platform.node().encode()).hexdigest(), str)
DISCORD_CLIENT_SECRET = _get_item(WEB_CONFIG, "discord_client_secret", None, str)
DISCORD_CLIENT_ID = _get_item(WEB_CONFIG, "discord_client_id", None)
if DISCORD_CLIENT_ID:
    DISCORD_CLIENT_ID = str(DISCORD_CLIENT_ID)
DISCORD_OAUTH_CALLBACK = _get_item(WEB_CONFIG, "discord_oauth_callback", f"{BASE_URL}/oauth2/callback", str)
DISCORD_API_VERSION = _get_item(WEB_CONFIG, "discord_api_version", 10, int)
DISCORD_API_BASE_URL = f"https://discord.com/api/v{DISCORD_API_VERSION}"
FORWARDED_ALLOW_IPS = _get_item(WEB_CONFIG, "forwarded_allow_ips", "*", str)

CORS_ALLOW_ORIGINS = _get_item(CORS_CONFIG, "allow_origins", ["*"])
CORS_ALLOW_METHODS = _get_item(CORS_CONFIG, "allow_methods", ["GET", "POST", "PATCH", "PUT", "DELETE"])
CORS_ALLOW_CREDENTIALS = _get_item(CORS_CONFIG, "allow_credentials", True)
CORS_ALLOW_HEADERS = _get_item(CORS_CONFIG, "allow_headers", ["*"])
