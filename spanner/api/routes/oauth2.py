import datetime
import secrets
import time
from typing import Annotated

import discord.utils
import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security.api_key import APIKeyCookie, APIKeyHeader

from spanner.share.database import DiscordOauthUser

from ..models.discord_ import AccessTokenResponse, User
from ..vars import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_OAUTH_CALLBACK

__all__ = ("router", "is_logged_in")


router = APIRouter(tags=["OAuth2"])
STATES: dict[str, str] = {}
RATELIMITER: dict[str, tuple[int, float]] = {}
# IP: (count, expires)

cookie_scheme = APIKeyCookie(name="session", auto_error=False)
bearer_scheme = APIKeyHeader(name="X-Spanner-Session", auto_error=False)


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


@router.get("/login")
async def login(req: Request, return_to: str) -> RedirectResponse:
    """
    Initiates the oauth2 login flow, by redirecting to discord.

    `:return_to` should be a URL to return the user to after successfully authenticating.
    """
    if not all((DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_OAUTH_CALLBACK)):
        raise HTTPException(503, "Oauth2 is misconfigured.")
    RATELIMITER.setdefault(req.client.host, (0, 0))
    count, expires = RATELIMITER[req.client.host]

    if count >= 5 and expires > time.time():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limited. Try again later.",
            headers={"Retry-After": str(round(expires - time.time()))},
        )

    if expires > time.time():
        RATELIMITER[req.client.host] = (count + 1, expires)
    else:
        RATELIMITER[req.client.host] = (1, time.time() + 30)

    state = secrets.token_urlsafe()
    STATES[state] = return_to

    url_base = (
        "https://discord.com/api/oauth2/authorize?"
        "client_id={!s}&redirect_uri={!s}&response_type=code&scope=identify guilds guilds.members.read"
        "&state={!s}&prompt=none"
    )
    url = url_base.format(DISCORD_CLIENT_ID, DISCORD_OAUTH_CALLBACK, state)
    res = RedirectResponse(url)
    res.set_cookie("state", state)
    return res


@router.get("/callback")
async def callback(
    req: Request, code: str, state: str = Query(...), state_cookie: str = Cookie(..., alias="state")
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
        print(
            "Fetching token using code %r (state %r), with client ID %r, secret %r, and redirect %r" % (
                code,
                state,
                DISCORD_CLIENT_ID,
                DISCORD_CLIENT_SECRET,
                DISCORD_OAUTH_CALLBACK,
            )
        )
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
                }
            )
        code_payload = AccessTokenResponse.model_validate(code_grant.json())
        if not all(x in code_payload.scope_array for x in ("identify", "guilds")):
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


@router.get("/whoami")
async def whoami(user: Annotated[DiscordOauthUser, is_logged_in]) -> User:
    """Fetches the current logged-in user's discord details"""
    async with httpx.AsyncClient(base_url="https://discord.com/api/v10") as client:
        res = await client.get("/users/@me", headers={"Authorization": f"Bearer {user.access_token}"})
        res.raise_for_status()
        return User.model_validate(res.json())


@router.get("/session")
async def session(user: Annotated[DiscordOauthUser, is_logged_in]):
    """Returns the current session token"""
    return {"token": user.session, "scopes": user.scope}
