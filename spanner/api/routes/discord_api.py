import time
from typing import Annotated

import discord.utils
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.responses import JSONResponse

from spanner.bot import bot
from spanner.share.database import DiscordOauthUser

from ..models.discord_ import BasicChannelInformation, PartialGuild, User
from ..vars import DISCORD_API_BASE_URL
from .oauth2 import is_logged_in

router = APIRouter(tags=["Discord API Proxy"])
RATELIMITER: dict[str, dict] = {}


def handle_ratelimit(req: Request):
    RATELIMITER.setdefault(req.client.host, {"remaining": 10, "reset": time.time() + 10})
    if RATELIMITER[req.client.host]["remaining"] <= 0:
        if RATELIMITER[req.client.host]["reset"] > time.time():
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You are being ratelimited. Please try again later.",
                headers={
                    "Retry-After": str(round(RATELIMITER[req.client.host]["reset"] - time.time())),
                }
            )
        RATELIMITER[req.client.host]["remaining"] = 10
        RATELIMITER[req.client.host]["reset"] = time.time() + 10
    RATELIMITER[req.client.host]["remaining"] -= 1
    return

ratelimit = Depends(handle_ratelimit)


@router.get("/users/@me", dependencies=[ratelimit])
async def get_me(user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> User:
    res.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=3600,stale-if-error=3600"
    if "identify" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: identify")
    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get("/users/@me", headers={"Authorization": f"Bearer {user.access_token}"})
        response.raise_for_status()
        return User.model_validate(response.json())


@router.get("/users/@me/guilds", dependencies=[ratelimit])
async def get_my_guilds(user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> list[PartialGuild]:
    if "guilds" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds")
    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            "/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        response.raise_for_status()
        res.headers["Cache-Control"] = "private,max-age=60,stale-while-revalidate=60,stale-if-error=60"
        return [PartialGuild.model_validate(guild) for guild in response.json()]


@router.get("/guilds/{guild_id}", dependencies=[ratelimit])
async def get_guild(guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> PartialGuild:
    if "guilds" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds")
    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            "/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        response.raise_for_status()
        for guild in response.json():
            if guild["id"] == str(guild_id):
                res.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=3600,stale-if-error=3600"
                return PartialGuild.model_validate(guild)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found")


@router.get("/guilds/{guild_id}/channels")
async def get_guild_channels(
    res: JSONResponse,
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    channel_types: list[int] = Query(None, alias="types"),
    minimum_user_permissions: int = Query(0),
    minimum_bot_permissions: int = Query(0),
) -> list[BasicChannelInformation]:
    if not bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")

    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")

    channels = list(guild.channels)
    resolved_channels = []
    if channel_types is not None:
        for channel in channels.copy():
            user_perms = channel.permissions_for(member)
            bot_perms = channel.permissions_for(guild.me)

            if channel.type.value not in channel_types:
                channels.remove(channel)
            elif user_perms < discord.Permissions(minimum_user_permissions):
                channels.remove(channel)

            elif bot_perms < discord.Permissions(minimum_bot_permissions):
                channels.remove(channel)
            else:
                resolved_channels.append(
                    BasicChannelInformation(
                        id=str(channel.id),
                        type=channel.type.value,
                        name=channel.name,
                        user_permissions=str(user_perms.value),
                        bot_permissions=bot_perms.value,
                        flags=channel.flags.value,
                    )
                )
    else:
        for channel in channels:
            user_perms = channel.permissions_for(member)
            bot_perms = channel.permissions_for(guild.me)
            resolved_channels.append(
                BasicChannelInformation(
                    id=str(channel.id),
                    type=channel.type.value,
                    name=channel.name,
                    user_permissions=str(user_perms.value),
                    bot_permissions=str(bot_perms.value),
                    flags=channel.flags.value,
                )
            )
    return resolved_channels


@router.get("/users/@me/guilds/{guild_id}/member", dependencies=[ratelimit])
async def get_my_guild_member(
    guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse
):
    if "guilds.members.read" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds.members.read")
    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            f"/users/@me/guilds/{guild_id}/member",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        response.raise_for_status()
        res.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=3600,stale-if-error=3600"
        return response.json()


@router.get("/users/@me/guilds/{guild_id}/permissions", dependencies=[ratelimit])
async def get_my_guild_permissions(
        guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in]
):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    return str(member.guild_permissions.value)
