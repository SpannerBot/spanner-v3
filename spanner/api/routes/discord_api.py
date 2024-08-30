import hashlib
import logging
import time
from hashlib import sha1
from typing import Annotated

import discord
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Header
from fastapi.responses import JSONResponse

from spanner.bot import bot
from spanner.share.database import DiscordOauthUser

from ..models.discord_ import ChannelInformation, PartialGuild, User, Member
from ..vars import DISCORD_API_BASE_URL
from ..ratelimiter import Ratelimiter, Bucket
from .oauth2 import is_logged_in

router = APIRouter(tags=["Discord API Proxy"])
logger = logging.getLogger("spanner.api.discord")
RATELIMITER = Ratelimiter()
DEFAULT_INTERNAL_KEY = "{req.method}:{req.client.host}"


def handle_ratelimit(req: Request) -> Bucket:
    key = sha1(DEFAULT_INTERNAL_KEY.format(req=req, authorization=req.headers.get("Authorization", "")).encode()).hexdigest()
    bucket = RATELIMITER.get_bucket(key)
    if not bucket:
        bucket = Bucket(key, 10, 10, time.time() + 10, 10)

    bucket.renew_if_not_expired()
    bucket.remaining -= 1
    RATELIMITER.buckets[key] = bucket

    if bucket.exhausted:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are being ratelimited by the server.",
            headers={
                "X-Ratelimit-Source": "internal",
                **bucket.generate_ratelimit_headers()
            }
        )
    return bucket


internal_ratelimit = Depends(handle_ratelimit)


@router.get("/users/@me", dependencies=[internal_ratelimit])
async def get_me(user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> User:
    """Fetches the discord profile of the currently logged in user."""
    _user = await bot.get_or_fetch_user(user.user_id)
    if _user:
        res.headers["X-Source"] = "internal"
        return User.from_user(_user)

    rl_key = sha1(f"{user.user_id}:{user.access_token}:/users/@me".encode()).hexdigest()
    if "identify" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: identify")

    bucket = RATELIMITER.get_bucket(rl_key)
    if bucket and bucket.exhausted:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are being ratelimited.",
            headers={
                "X-Ratelimit-Source": "discord.preemptive",
                **bucket.generate_ratelimit_headers()
            }
        )

    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        logger.info("Sending request to discord API for /users/@me")
        response = await client.get("/users/@me", headers={"Authorization": f"Bearer {user.access_token}"})
        bucket = RATELIMITER.from_discord_headers(response.headers, key=rl_key)
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "X-Ratelimit-Source": "discord",
                    **bucket.generate_ratelimit_headers()
                }
            )
        response.raise_for_status()
        res.headers["X-Source"] = "discord"
        return User.model_validate(response.json())


@router.get("/users/@me/guilds", dependencies=[internal_ratelimit])
async def get_my_guilds(user: Annotated[DiscordOauthUser, is_logged_in]) -> list[PartialGuild]:
    """Returns a list of partial guilds that the logged in user is in."""
    if "guilds" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds")

    rl_key = sha1(f"{user.user_id}:{user.access_token}:/users/@me/guilds".encode()).hexdigest()
    bucket = RATELIMITER.get_bucket(rl_key)
    if bucket and bucket.exhausted:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are being ratelimited.",
            headers={
                "X-Ratelimit-Source": "discord.preemptive",
                **bucket.generate_ratelimit_headers()
            }
        )

    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            "/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        bucket = RATELIMITER.from_discord_headers(response.headers, key=rl_key)
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "X-Ratelimit-Source": "discord",
                    **bucket.generate_ratelimit_headers(),
                }
            )
        response.raise_for_status()
        return [PartialGuild.model_validate(guild) for guild in response.json()]


@router.get("/users/{user_id}", dependencies=[internal_ratelimit, is_logged_in])
async def get_user(user_id: int, res: JSONResponse, if_none_match: str = Header(None)) -> User:
    """
    Fetches a user by ID.

    This endpoint makes use of an etag header - if the display name/avatar hash has not changed,
    the server will return a 304 Not Modified response.
    """
    user = await bot.get_or_fetch_user(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found.")
    res.headers["etag"] = hashlib.md5(f"{user.display_name}{user.display_avatar}".encode()).hexdigest()
    if if_none_match and if_none_match == res.headers["etag"]:
        raise HTTPException(status.HTTP_304_NOT_MODIFIED)
    return User.from_user(user)


@router.get("/guilds/{guild_id}", dependencies=[internal_ratelimit])
async def get_guild(guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse) -> PartialGuild:
    """
    Fetches a guild by ID.

    This endpoint will attempt to fetch the guild object from the bot using the gateway first.
    If that fails (i.e. the bot is not in the guild), then it will query discord's API to fetch the guild object.
    This means you may be subject to stricter ratelimits.
    """
    guild = await discord.utils.get_or_fetch(bot, "guild", guild_id, default=None)
    if guild:
        res.headers["X-Source"] = "internal"
        member = await discord.utils.get_or_fetch(guild, "member", user.user_id, default=None)
        if member:
            return PartialGuild.from_member(member)
        return PartialGuild.from_guild(guild)

    if "guilds" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds")

    rl_key = sha1(f"{user.user_id}:{user.access_token}:/users/@me/guilds".encode()).hexdigest()
    bucket = RATELIMITER.get_bucket(rl_key)
    if bucket and bucket.exhausted:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are being ratelimited.",
            headers={
                "X-Ratelimit-Source": "discord.preemptive",
                **bucket.generate_ratelimit_headers()
            }
        )

    async with httpx.AsyncClient(base_url=DISCORD_API_BASE_URL) as client:
        response = await client.get(
            "/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        bucket = RATELIMITER.from_discord_headers(response.headers, key=rl_key)
        if response.status_code == 429:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="You are being ratelimited by discord.",
                headers={
                    "X-Ratelimit-Source": "discord",
                    **bucket.generate_ratelimit_headers(),
                }
            )
        response.raise_for_status()
        for guild in response.json():
            if guild["id"] == str(guild_id):
                return PartialGuild.model_validate(guild)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found")


@router.get("/guilds/{guild_id}/channels", dependencies=[internal_ratelimit])
async def get_guild_channels(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    channel_types: list[int] = Query(None, alias="types"),
    minimum_user_permissions: int = Query(0),
    minimum_bot_permissions: int = Query(0),
) -> list[ChannelInformation]:
    """
    Returns a list of channels in a guild that match the given filters
    """
    guild: discord.Guild = await discord.utils.get_or_fetch(bot, "guild", guild_id, default=None)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id, default=None)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")

    channels = list(guild.channels)
    resolved_channels = []
    for channel in channels:
        user_perms = channel.permissions_for(member)
        bot_perms = channel.permissions_for(guild.me)

        if channel_types and channel.type.value not in channel_types:
            continue
        elif user_perms < discord.Permissions(minimum_user_permissions):
            continue
        elif bot_perms < discord.Permissions(minimum_bot_permissions):
            continue

        resolved_channels.append(
            ChannelInformation.from_channel(channel)
        )
    return resolved_channels


@router.get("/guilds/{guild_id}/@me", dependencies=[internal_ratelimit])
async def get_my_guild_member(
    guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], res: JSONResponse
):
    """
    Fetches the current user's member object for the given guild.

    This endpoint will attempt to fetch the member object from the bot using the gateway first.
    If that fails (i.e. the bot is not in the guild, or the member could not be found in the guild),
    then it will query discord's API to fetch the member object.

    If the member cannot be found by the bot, you may be subject to discord's ratelimit.
    This endpoint is not cached.
    """
    guild: discord.Guild = await discord.utils.get_or_fetch(bot, "guild", guild_id, default=None)
    if guild:
        member = await discord.utils.get_or_fetch(guild, "member", user.user_id, default=None)
        if member:
            res.headers["X-Source"] = "internal"
            return Member.from_member(member)

    if "guilds.members.read" not in user.scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing required scope: guilds.members.read")

    rl_key = sha1(f"{user.user_id}:{user.access_token}:/users/@me/guilds/{guild_id}/member".encode()).hexdigest()
    bucket = RATELIMITER.get_bucket(rl_key)
    if bucket and bucket.exhausted:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are being ratelimited.",
            headers={
                "X-Ratelimit-Source": "discord.preemptive",
                **bucket.generate_ratelimit_headers()
            }
        )

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
                    "X-Ratelimit-Source": "discord",
                    **bucket.generate_ratelimit_headers(),
                }
            )
        response.raise_for_status()
        return response.json()


@router.get("/guilds/{guild_id}/bot", dependencies=[internal_ratelimit, is_logged_in])
async def get_my_guild_bot(
    guild_id: int
) -> Member:
    """
    Fetches the bot's member object for the given guild.
    """
    guild: discord.Guild = await discord.utils.get_or_fetch(bot, "guild", guild_id, default=None)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    me = guild.me
    return Member.from_member(me)


@router.get("/guilds/{guild_id}/@me/permissions", dependencies=[internal_ratelimit])
async def get_my_guild_permissions(
        res: JSONResponse, guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in]
):
    """
    Fetches the current permissions value for the current user in a given server.

    This endpoint is explicitly not cached.
    """
    res.headers["Cache-Control"] = "no-cache,no-store"
    guild: discord.Guild = await discord.utils.get_or_fetch(bot, "guild", guild_id, default=None)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    return str(member.guild_permissions.value)
