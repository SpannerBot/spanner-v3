import math
import time
from typing import Annotated

import discord
import httpx
from discord.http import Route
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from spanner.bot import bot
from spanner.share.database import DiscordOauthUser

from ..models.discord_ import BasicChannelInformation, PartialGuild, User
from ..vars import DISCORD_API_BASE_URL
from .oauth2 import is_logged_in

router = APIRouter(tags=["Discord API Proxy"])
RATELIMITER: dict[str, dict] = {}
DISCORD_RATELIMITER = {}


def handle_ratelimit(req: Request):
    RATELIMITER.setdefault(req.client.host, {"remaining": 10, "reset": time.time() + 10})
    if RATELIMITER[req.client.host]["remaining"] <= 0:
        if RATELIMITER[req.client.host]["reset"] > time.time():
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You are being ratelimited. Please try again later.",
                headers={
                    "Retry-After": str(math.ceil(RATELIMITER[req.client.host]["reset"] - time.time())),
                    "X-Ratelimit-Source": "Internal"
                }
            )
        RATELIMITER[req.client.host]["remaining"] = 10
        RATELIMITER[req.client.host]["reset"] = time.time() + 10
    RATELIMITER[req.client.host]["remaining"] -= 1
    return


ratelimit = Depends(handle_ratelimit)


@router.get("/users/@me", dependencies=[ratelimit])
async def get_me(user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> User:
    """Fetches the discord profile of the currently logged in user."""
    _user = await bot.get_or_fetch_user(user.user_id)
    if _user:
        return User.from_user(_user)
    res.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=3600,stale-if-error=3600"
    if "identify" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: identify")
    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get("/users/@me", headers={"Authorization": f"Bearer {user.access_token}"})
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "Retry-After": str(response.headers.get("X-Ratelimit-Reset-After", 10)),
                }
            )
        response.raise_for_status()
        return User.model_validate(response.json())


@router.get("/users/@me/guilds", dependencies=[ratelimit])
async def get_my_guilds(user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> list[PartialGuild]:
    """Returns a list of partial guilds that the logged in user is in."""
    if "guilds" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds")

    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            "/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "Retry-After": str(response.headers.get("X-Ratelimit-Reset-After", 10)),
                }
            )
        response.raise_for_status()
        res.headers["Cache-Control"] = "private,max-age=60,stale-while-revalidate=60,stale-if-error=60"
        return [PartialGuild.model_validate(guild) for guild in response.json()]


@router.get("/users/{user_id}", dependencies=[ratelimit])
async def get_user(user_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> User:
    """Fetches a user by ID."""
    user = await bot.get_or_fetch_user(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found.")
    return User.from_user(user)


@router.get("/guilds/{guild_id}", dependencies=[ratelimit])
async def get_guild(guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> PartialGuild:
    guild = await discord.utils.get_or_fetch(bot, "guild", guild_id)
    if guild:
        res.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=3600,stale-if-error=3600"
        member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
        if member:
            return PartialGuild.from_member(member)
        return PartialGuild.from_guild(guild)

    if "guilds" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds")
    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            "/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "Retry-After": str(response.headers.get("X-Ratelimit-Reset-After")),
                }
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


@router.get("/guilds/{guild_id}/@me", dependencies=[ratelimit])
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
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "Retry-After": str(response.headers.get("X-Ratelimit-Reset-After", 10)),
                }
            )
        response.raise_for_status()
        res.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=3600,stale-if-error=3600"
        return response.json()


@router.get("/guilds/{guild_id}/bot", dependencies=[ratelimit])
async def get_my_guild_bot(
    guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse
):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    me = guild.me
    data = {
        "user": {
            "id": str(me.id),
            "username": me.name,
            "discriminator": me.discriminator,
            "global_name": me.global_name,
            "avatar": me.avatar,
            "bot": me.bot,
            "system": me.system,
            "flags": me.flags.value,
            "public_flags": me.public_flags.value,
        },
        "nick": me.nick,
        "roles": list(map(lambda r: str(r.id), me.roles)),
        "joined_at": me.joined_at.isoformat(),
        "mute": me.mute,
        "deaf": me.deaf,
        "flags": me.flags.value,
        "permissions": str(me.guild_permissions.value)
    }
    return data


@router.get("/guilds/{guild_id}/@me/permissions", dependencies=[ratelimit])
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
