import logging
import tomllib
from pathlib import Path

__all__ = ("load_config",)
log = logging.getLogger("share.config")


def load_config():
    file = Path.cwd() / "config.toml"
    if not file.exists():
        raise FileNotFoundError("No config.toml file exists in the current directory.")

    with file.open("rb") as fd:
        config = tomllib.load(fd)
        if not config.get("spanner"):
            raise ValueError("No [spanner] section in the config.toml file.")
        if "token" not in config["spanner"]:
            raise ValueError("No token in the [spanner] section of the config.toml file.")

    config.setdefault("logging", {})
    config.setdefault("cogs", {})
    config.setdefault("database", {"url": "sqlite://./spanner.db"})
    config["cogs"].setdefault("meta", {"support_guild_id": None})

    return config
