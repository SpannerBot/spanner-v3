import typing
from typing import Annotated

import discord
import jwt
from fastapi import Cookie, Depends, HTTPException, Header, Path, Request, status

from spanner.api.vars import ALGORITHM, SECRET_KEY
from spanner.share.database import DiscordOauthUser

__all__ = (
    "logged_in_user",
    "LoggedInUserDependency",
    "STATE_KEYS",
    "user_has_permissions",
)

STATE_KEYS = {}


async def logged_in_user(
    req: Request, token: str = Cookie(None, alias="_token"), x_session: str = Header(None, alias="X-Session")
) -> DiscordOauthUser:
    url = req.url_for("discord_authorise").include_query_params(from_url=req.url.path)
    reauth = HTTPException(status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": str(url)})
    token = token or x_session
    if not token:
        reauth.detail = "Please log in with discord: %s" % str(url)
        raise reauth

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = await DiscordOauthUser.get_or_none(id=int(payload["sub"]))
        if not user:
            raise HTTPException(404, "User not found.")
        return user
    except jwt.ExpiredSignatureError:
        reauth.detail = "Token expired. %s" % str(url)
        raise reauth
    except jwt.InvalidTokenError:
        reauth.detail = "Invalid token. %s" % str(url)
        raise reauth


def user_has_permissions(perms: discord.Permissions | int) -> Depends:
    if isinstance(perms, int):
        perms = discord.Permissions(perms)

    async def inner(
        req: Request, guild_id: Annotated[int, Path(...)], user: Annotated[DiscordOauthUser, Depends(logged_in_user)]
    ):
        guild = req.app.bot.get_guild(guild_id)
        if not guild:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Guild not found.")
        try:
            member = await guild.fetch_member(user.id)
        except discord.NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"You are not in {guild.name!r}.")
        except discord.HTTPException:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden (unable to check membership)")
        else:
            if member.guild_permissions < perms:
                raise HTTPException(status.HTTP_403_FORBIDDEN, f"Forbidden (missing permissions: {perms.value})")
        return member

    return Depends(inner)


LoggedInUserDependency = typing.Annotated[DiscordOauthUser, Depends(logged_in_user)]
