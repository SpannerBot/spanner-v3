import discord.utils
from fastapi import APIRouter, HTTPException, status
from typing import Annotated

from starlette.responses import Response

from .oauth2 import is_logged_in
from spanner.share.database import DiscordOauthUser, GuildConfig, GuildConfigPydantic
from spanner.bot import bot

router = APIRouter(tags=["Configuration"])


@router.get("/{guild_id}")
async def get_guild_config(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in]
) -> GuildConfigPydantic:
    """
    Get the configuration for the given guild.
    """
    if not bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")

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
        guild_id: int
):
    """Checks that the bot is in the target server."""
    if not bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")

    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
