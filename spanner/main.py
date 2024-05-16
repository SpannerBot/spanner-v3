import datetime
import logging
import os
import sys
import time
import tomllib
from pathlib import Path

import discord
from discord.ext import commands
from rich.logging import RichHandler

sys.path.append(".")
sys.path.append("..")

# Load the configuration file
CONFIG_FILE = Path.cwd() / "config.toml"
if not CONFIG_FILE.exists():
    logging.critical("No config.toml file exists in the current directory.")
    sys.exit(1)

with CONFIG_FILE.open("rb") as fd:
    CONFIG = tomllib.load(fd)
CONFIG.setdefault("logging", {})
CONFIG_SPANNER = CONFIG.get("spanner")
if not CONFIG_SPANNER:
    logging.critical("No [spanner] section in the config.toml file.")
    sys.exit(1)

if "token" not in CONFIG_SPANNER:
    logging.critical("No token in the [spanner] section of the config.toml file.")
    sys.exit(1)

CONFIG_LOGGING = CONFIG["logging"]
logging.basicConfig(
    level=CONFIG_LOGGING.get("level", "INFO"),
    format=CONFIG_LOGGING.get("format", "%(asctime)s:%(name)s:%(levelname)s: %(message)s"),
    datefmt=CONFIG_LOGGING.get("datefmt", "%Y-%m-%d %H:%M:%S"),
    handlers=[RichHandler(logging.INFO, rich_tracebacks=True, markup=True, show_time=False, show_path=False)],
)
if "file" in CONFIG_LOGGING:
    handler = logging.FileHandler(
        CONFIG_LOGGING["file"]["name"],
        CONFIG_LOGGING["file"].get("mode", "a"),
        CONFIG_LOGGING["file"].get("encoding", "utf-8"),
    )
    if "level" in CONFIG_LOGGING["file"]:
        handler.setLevel(CONFIG["logging"]["file"]["level"])
    handler.setFormatter(
        logging.Formatter(CONFIG_LOGGING.get("format", "%(asctime)s:%(name)s:%(levelname)s: %(message)s"))
    )
    logging.getLogger().addHandler(handler)

for logger in CONFIG_LOGGING.get("silence", []):
    logging.getLogger(logger).setLevel(logging.WARNING)
    logging.getLogger(logger).warning("Level for this logger set to WARNING via config.toml[logging.silence].")


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("s!", "S!"),
    strip_after_prefix=True,
    case_insensitive=True,
    debug_guilds=CONFIG_SPANNER.get("debug_guilds", None),
    intents=discord.Intents.all(),
    status=discord.Status.idle,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
)
log = logging.getLogger("spanner.runtime")

if "cogs" not in CONFIG_SPANNER:
    cogs = ["cogs." + x.name[:-3] for x in (Path.cwd() / "cogs").glob("*.py")]
else:
    cogs = CONFIG_SPANNER["cogs"]

log.info("Preparing to load cogs: %s", ", ".join(cogs))
for cog in ["jishaku", *cogs]:
    s = time.perf_counter()
    try:
        s = time.perf_counter()  # redefine it just for this block
        bot.load_extension(cog)
        e = time.perf_counter()
    except discord.ExtensionFailed as e:
        en = time.perf_counter()
        log.error("Failed to load cog %r in %.2fms: %s", cog, (en - s) * 1000, e, exc_info=True)
    else:
        log.info("Loaded %r in %.2fms", cog, (e - s) * 1000)


@bot.event
async def on_ready():
    log.info("Spanner v3 is now connected to discord as %s." % bot.user.name)
    log.info("Spanner can see {:,} users in {:,} guilds.".format(len(bot.users), len(bot.guilds)))
    print("Invite %s: %s" % (bot.user.name, discord.utils.oauth_url(bot.user.id)))
    if bot.debug_guilds:
        eligible = list(map(lambda gid: getattr(bot.get_guild(gid), "name", str(gid)), bot.debug_guilds))
        log.warning("Slash commands will only be available in the following servers: %r", ", ".join(eligible))

    log.info(
        "%d+%d total commands across %d cogs (%d modules) are loaded.",
        len(bot.application_commands),
        len(bot.commands),
        len(bot.cogs),
        len(bot.extensions),
    )


@bot.listen()
async def on_application_command(ctx: discord.ApplicationContext):
    ctx.start = time.perf_counter()
    log.info(
        "%r (%s) used application command %r (%s) in %r (%s), %r (%s), with interaction ID %s.",
        ctx.user.name,
        ctx.user.id,
        ctx.command.qualified_name,
        ctx.command.qualified_id,
        ctx.channel.name,
        ctx.channel.id,
        (ctx.guild or ctx.channel).name,
        (ctx.guild or ctx.channel).id,
        ctx.interaction.id,
    )


@bot.listen()
async def on_application_command_completion(ctx: discord.ApplicationContext):
    if not hasattr(ctx, "start"):
        log.warning("Context missing start attribute.")
        ctx.start = time.perf_counter()

    log.info(
        "Command %r (interaction ID %d) from %r completed in %.2fms.",
        getattr(ctx.command, "qualified_name", getattr(ctx.command, "name", str(ctx.command))),
        ctx.interaction.id,
        ctx.user.name,
        (time.perf_counter() - ctx.start) * 1000,
    )


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    if hasattr(error, "original"):
        error = error.original

    if not hasattr(ctx, "start"):
        log.warning("Context missing start attribute.")
        ctx.start = time.perf_counter()

    if isinstance(error, discord.NotFound):
        return

    if isinstance(error, commands.CommandOnCooldown):
        time_remaining = error.retry_after
        expires = discord.utils.utcnow() + datetime.timedelta(seconds=time_remaining)
        return await ctx.respond(
            "\N{stopwatch} This command is on cooldown until {}.".format(discord.utils.format_dt(expires, "R")),
            ephemeral=True,
        )
    elif isinstance(error, (commands.BotMissingPermissions, commands.MissingPermissions)):
        return await ctx.respond(f"\N{cross mark} {error}", ephemeral=True)
    elif isinstance(error, commands.MaxConcurrencyReached):
        return await ctx.respond(
            "\N{cross mark} This command is overloaded. Please wait a while and try again.", ephemeral=True
        )

    log.error(
        "Command %r (interaction ID %d) from %r failed: %s",
        getattr(ctx.command, "qualified_name", getattr(ctx.command, "name", str(ctx.command))),
        ctx.interaction.id,
        ctx.user.name,
        error,
        exc_info=error,
    )
    return await ctx.respond(
        f"\u2757 There was an error running your command (`{error!r}`). The developer has been notified.",
        ephemeral=True,
    )


@bot.slash_command()
async def ping(ctx: discord.ApplicationContext):
    """Checks the latency between the bot and discord."""
    t = f"WebSocket: `{round(ctx.bot.latency * 1000)}ms`\nHTTP: `pinging`"
    start_p = time.perf_counter()
    await ctx.respond(t, ephemeral=True)
    end_p = time.perf_counter()
    t = t[:-8] + f"{round((end_p - start_p) * 1000)}ms`"
    return await ctx.edit(content=t)


if __name__ == "__main__":
    bot.run(CONFIG_SPANNER["token"])
