import toml
import discord
import time
from discord.ext import commands
import sys
import logging
from pathlib import Path

# Load the configuration file
CONFIG_FILE = Path.cwd() / "config.toml"
if not CONFIG_FILE.exists():
    logging.critical("No config.toml file exists in the current directory.")
    sys.exit(1)

CONFIG = toml.load(CONFIG_FILE)
CONFIG.setdefault("logging", {})
CONFIG_SPANNER = CONFIG.get("spanner")
if not CONFIG_SPANNER:
    logging.critical("No [spanner] section in the config.toml file.")
    sys.exit(1)

if "token" not in CONFIG_SPANNER:
    logging.critical("No token in the [spanner] section of the config.toml file.")
    sys.exit(1)

if CONFIG["logging"]:
    CONFIG_LOGGING = CONFIG["logging"]
    logging.basicConfig(
        level=CONFIG_LOGGING.get("level", "INFO"),
        format=CONFIG_LOGGING.get("format", "%(asctime)s:%(name)s:%(levelname)s: %(message)s"),
        datefmt=CONFIG_LOGGING.get("datefmt", "%Y-%m-%d %H:%M:%S"),
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
            logging.Formatter(
                CONFIG_LOGGING.get(
                    "format", "%(asctime)s:%(name)s:%(levelname)s: %(message)s"
                )
            )
        )
        logging.getLogger().addHandler(handler)


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("s!", "S!"),
    strip_after_prefix=True,
    case_insensitive=True,
    debug_guilds=CONFIG_SPANNER.get("debug_guilds", None),
    intents=discord.Intents.all(),
    status=discord.Status.idle(),
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, )
)
log = logging.getLogger("spanner.runtime")

if "cogs" not in CONFIG_SPANNER:
    cogs = ["cogs." + x.name[:-3] for x in (Path.cwd() / "cogs").glob("*.py")]
else:
    cogs = CONFIG_SPANNER["cogs"]

log.info("Preparing to load cogs: %s", ", ".join(cogs))
for cog in cogs:
    s = time.perf_counter()
    try:
        s = time.perf_counter()  # redefine it just for this block
        bot.load_extension(cog)
        e = time.perf_counter()
    except discord.ExtensionFailed as e:
        en = time.perf_counter()
        log.error("Failed to load cog %r in %.2fms: %s", cog, (en - s) * 1000, e, exc_info=True)
    else:
        log.debug("Loaded %r in %.2fms", cog, (e - s) * 1000)


@bot.event
async def on_ready():
    log.info("Spanner v3 is now connected to discord as %s." % bot.user.name)
    log.info("Spanner can see {:,} users in {:,} guilds.".format(len(bot.users), len(bot.guilds)))
    print("Invite %s: %s" % (bot.user.name, discord.utils.oauth_url(bot.user.id)))
    if bot.debug_guilds:
        eligible = list(
            map(lambda gid: getattr(bot.get_guild(gid), "name", str(gid)), bot.debug_guilds)
        )
        log.warning("Slash commands will only be available in the following servers: %r", ", ".join(eligible))

    log.info(
        "%d total commands across %d cogs (%d modules) are loaded.",
        len(bot.commands), 
        len(bot.cogs), 
        len(bot.extensions)
    )


@bot.listen()
async def on_application_command(ctx: discord.ApplicationCommand):
    ctx.start = time.perf_counter()
    log.info(
        "%r (%d) used application command %r (%d) in %r (%d), %r (%d), with interaction ID %d.",
        ctx.user.name,
        ctx.user.id,
        ctx.command.qualified_name,
        ctx.command.qualified_id,
        ctx.channel.name,
        ctx.channel.id,
        (ctx.guild or ctx.channel).name,
        (ctx.guild or ctx.channel).id,
        ctx.interaction.id
    )


@bot.listen()
async def on_application_command_completion(ctx: discord.ApplicationCommand):
    if not hasattr(ctx, "start"):
        log.warning("Context missing start attribute.")
        ctx.start = time.perf_counter()

    log.info(
        "Command %r (interaction ID %d) from %r completed in %.2fms.",
        ctx.command.qualified_name,
        ctx.interaction.id,
        ctx.user.name,
        (time.perf_counter() - ctx.start) * 1000
    )


@bot.event
async def on_application_command_error(ctx: discord.ApplicationCommand, error: discord.DiscordException):
    if hasattr(error, "original"):
        error = error.original
    
    if not hasattr(ctx, "start"):
        log.warning("Context missing start attribute.")
        ctx.start = time.perf_counter()
    
    if isinstance(error, commands.CommandOnCooldown):
        pass
    
    log.error(
        "Command %r (interaction ID %d) from %r failed: %s",
        ctx.command.qualified_name,
        ctx.interaction.id,
        ctx.user.name,
        error
    )
