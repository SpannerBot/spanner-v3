import datetime
import secrets
import time
from hashlib import sha1
from typing import Annotated

import discord.utils
import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security.api_key import APIKeyCookie, APIKeyHeader
from starlette.responses import JSONResponse

from spanner.share.database import DiscordOauthUser

from ..models.discord_ import AccessTokenResponse, User
from ..ratelimiter import Bucket, Ratelimiter
from ..vars import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_OAUTH_CALLBACK

__all__ = ("router", "is_logged_in")


router = APIRouter(tags=["OAuth2"])
STATES: dict[str, str] = {}

cookie_scheme = APIKeyCookie(name="session", auto_error=False)
bearer_scheme = APIKeyHeader(name="X-Spanner-Session", auto_error=False)

RATELIMITER = Ratelimiter()
DEFAULT_INTERNAL_KEY = "{req.method}:{req.client.host}"


def handle_ratelimit(req: Request) -> Bucket:
    key = sha1(
        DEFAULT_INTERNAL_KEY.format(req=req, authorization=req.headers.get("Authorization", "")).encode()
    ).hexdigest()
    bucket = RATELIMITER.get_bucket(key)
    if not bucket:
        bucket = Bucket(key, 5, 5, time.time() + 10, 10)

    bucket.renew_if_not_expired()
    bucket.remaining -= 1
    RATELIMITER.buckets[key] = bucket

    if bucket.exhausted:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You are being ratelimited by the server.",
            headers={"X-Ratelimit-Source": "internal", **bucket.generate_ratelimit_headers()},
        )
    return bucket


async def _is_authenticated(
    session_cookie: str | None = Depends(cookie_scheme), session_header: str | None = Depends(bearer_scheme)
) -> DiscordOauthUser:
    session_token = session_header or session_cookie
    if session_token is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing session cookie")

    user = await DiscordOauthUser.get_or_none(session=session_token)
    if user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail=f"Invalid session {session_token!r}. Clear your cookies and try again."
        )

    if user.expires_at < discord.utils.utcnow().timestamp():
        await user.delete()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Expired session. Clear your cookies and try again.")

    return user


is_logged_in = Depends(_is_authenticated)


@router.get("/login", dependencies=[Depends(handle_ratelimit)])
async def login(req: Request, return_to: str) -> RedirectResponse:
    """
    Initiates the oauth2 login flow, by redirecting to discord.

    `:return_to` should be a URL to return the user to after successfully authenticating.
    """
    if not all((DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_OAUTH_CALLBACK)):
        raise HTTPException(503, "Oauth2 is misconfigured.")
    state = secrets.token_urlsafe()
    STATES[state] = return_to

    url_base = (
        "https://discord.com/api/oauth2/authorize?"
        "client_id={!s}&redirect_uri={!s}&response_type=code&scope=identify guilds guilds.members.read"
        "&state={!s}&prompt=none"
    )
    url = url_base.format(DISCORD_CLIENT_ID, DISCORD_OAUTH_CALLBACK, state)
    res = RedirectResponse(url)
    res.set_cookie("state", state, httponly=True, expires=600)
    return res


@router.get("/invite", include_in_schema=False, dependencies=[Depends(handle_ratelimit)])
async def invite(guild_id: int | None = None, return_to: str | None = None) -> RedirectResponse:
    if not all((DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_OAUTH_CALLBACK)):
        raise HTTPException(503, "Oauth2 is misconfigured.")

    state = secrets.token_urlsafe()
    STATES[state] = return_to
    res = RedirectResponse(
        discord.utils.oauth_url(
            DISCORD_CLIENT_ID,
            permissions=discord.Permissions(9896105209073),
            guild=discord.Object(guild_id) if guild_id else None,
            scopes=["bot", "identify", "guilds", "guilds.members.read"],
            disable_guild_select=guild_id is not None,
            redirect_uri=DISCORD_OAUTH_CALLBACK,
        )
        + "&state="
        + state
    )
    res.set_cookie("state", state, httponly=True, expires=600)
    return res


@router.get("/callback", dependencies=[Depends(handle_ratelimit)])
async def callback(
    code: str, state: str = Query(...), state_cookie: str = Cookie(..., alias="state")
) -> RedirectResponse:
    """
    Callback for the oauth2 login flow, redirects to the return_to URL.

    `:code` is the code returned by discord
    `:state` is the state cookie set by the login endpoint.

    This endpoint will return a 307 redirect, with a session cookie set.
    """
    if state not in STATES or state_cookie != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")

    return_to = STATES[state]
    del STATES[state]

    async with httpx.AsyncClient(base_url="https://discord.com/api/v10") as client:
        code_grant = await client.post(
            "/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_OAUTH_CALLBACK,
            },
            auth=(DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if code_grant.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Failed to fetch token from upstream",
                    "status": code_grant.status_code,
                    "response": code_grant.json(),
                },
            )
        code_payload = AccessTokenResponse.model_validate(code_grant.json())
        if not all(x in code_payload.scope_array for x in ("identify",)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required scopes")

        user_data = await client.get("/users/@me", headers={"Authorization": f"Bearer {code_payload.access_token}"})
        user_data.raise_for_status()
        user_data = User.model_validate(user_data.json())

        obj = await DiscordOauthUser.create(
            user_id=user_data.id,
            access_token=code_payload.access_token,
            refresh_token=code_payload.refresh_token,
            expires_at=(discord.utils.utcnow() + datetime.timedelta(seconds=code_payload.expires_in)).timestamp(),
            session=secrets.token_urlsafe(),
            scope=code_payload.scope,
        )

    res = RedirectResponse(return_to)
    res.set_cookie("session", obj.session, expires=code_payload.expires_in, samesite="lax")
    res.delete_cookie("state")
    return res


@router.get("/session")
async def session(user: Annotated[DiscordOauthUser, is_logged_in]):
    """Returns the current session token"""
    return {"token": user.session, "user_id": str(user.user_id), "scopes": user.scope, "expires_at": user.expires_at}


@router.post("/session/refresh", dependencies=[Depends(handle_ratelimit)])
async def refresh_session(res: JSONResponse, user: Annotated[DiscordOauthUser, is_logged_in]):
    """Refreshes the current session token"""
    async with httpx.AsyncClient(base_url="https://discord.com/api/v10") as client:
        refresh = await client.post(
            "/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": user.refresh_token,
            },
            auth=(DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if refresh.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Failed to fetch token from upstream",
                    "status": refresh.status_code,
                    "response": refresh.json(),
                },
            )
        refresh_payload = AccessTokenResponse.model_validate(refresh.json())

        user.access_token = refresh_payload.access_token
        if refresh_payload.refresh_token != user.refresh_token:
            user.refresh_token = refresh_payload.refresh_token
        if refresh_payload.scope != user.scope:
            user.scope = refresh_payload.scope
        user.expires_at = (discord.utils.utcnow() + datetime.timedelta(seconds=refresh_payload.expires_in)).timestamp()
        await user.save()

    res.set_cookie("session", user.session, expires=refresh_payload.expires_in, samesite="lax")
    return {"token": user.session, "user_id": str(user.user_id), "scopes": user.scope, "expires_at": user.expires_at}


@router.delete("/session")
async def delete_session(user: Annotated[DiscordOauthUser, is_logged_in]):
    """Deletes the current session token"""
    try:
        async with httpx.AsyncClient(base_url="https://discord.com/api/v10") as client:
            await client.post(
                "/oauth2/token/revoke",
                data={"token": user.access_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError:
        pass
    finally:
        await user.delete()
    return {"message": "Session deleted."}
