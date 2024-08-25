import discord.utils
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Annotated

from starlette.responses import Response

from .oauth2 import is_logged_in
from spanner.share.database import DiscordOauthUser, GuildConfig, GuildConfigPydantic, GuildNickNameModerationPydantic, GuildNickNameModeration
from spanner.bot import bot as __bot, CustomBridgeBot


def bot_is_ready():
    def inner() -> CustomBridgeBot:
        if not __bot.is_ready():
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")
        return __bot
    return Depends(inner)


router = APIRouter(tags=["Configuration"])


@router.get("/{guild_id}")
async def get_guild_config(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    bot: Annotated[CustomBridgeBot, bot_is_ready]
) -> GuildConfigPydantic:
    """
    Get the configuration for the given guild.
    """
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")

    config, _ = await GuildConfig.get_or_create(id=guild_id)

    return await GuildConfigPydantic.from_tortoise_orm(config)


@router.get("/{guild_id}/presence", status_code=status.HTTP_204_NO_CONTENT)
async def get_guild_presence(
        guild_id: int,
        bot: Annotated[CustomBridgeBot, bot_is_ready]
):
    """Checks that the bot is in the target server."""
    if not bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")

    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guild_id}/nickname-moderation")
async def get_nickname_moderation(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    bot: Annotated[CustomBridgeBot, bot_is_ready]
) -> GuildNickNameModerationPydantic:
    """
    Get the nickname moderation configuration for the given guild.
    """
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")

    config = await GuildNickNameModeration.get_or_none(guild_id=guild_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Nickname moderation configuration not found.")
    return await GuildNickNameModerationPydantic.from_tortoise_orm(config)
