import datetime
import logging
import secrets

import aiohttp
import discord
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from spanner.share.database import DiscordOauthUser

from ..auth import STATE_KEYS
from ..vars import ACCESS_TOKEN_EXPIRE_SECONDS, ALGORITHM, CLIENT_SECRET, OAUTH_URL, SECRET_KEY

api = APIRouter(prefix="/api/oauth", tags=["OAuth"])
log = logging.getLogger("spanner.api.oauth")


@api.get("/callback/discord", include_in_schema=False)
async def discord_authorise(req: Request, code: str = None, state: str = None, from_url: str = None):
    if not req.app.bot.is_ready() or not CLIENT_SECRET:
        raise HTTPException(503, "Not ready.", {"Retry-After": "30"})
    if not all((code, state)):
        log.info(
            "Request %r had no code (%r) or state (%r) - redirecting to login from %r.",
            req,
            code,
            state,
            from_url or "/",
        )
        state_key = secrets.token_urlsafe()
        if from_url and "oauth/callback/discord" in from_url:
            from_url = "https://discord.gg/TveBeG7"
        STATE_KEYS[state_key] = from_url
        r = RedirectResponse(
            url=OAUTH_URL.format(
                client_id=req.app.bot.user.id,
                redirect_uri=str(req.base_url) + "api/oauth/callback/discord",
                state=state_key,
            )
            + "&prompt=none"
        )
        r.set_cookie("_state", state_key, max_age=300, httponly=True, samesite="lax")
        return r
    elif state not in STATE_KEYS:
        raise HTTPException(403, "Invalid or expired request.")
    elif state != req.cookies.get("_state"):
        raise HTTPException(403, "Unable to authenticate request is legitimate.")
    to = STATE_KEYS.pop(state)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(req.base_url) + "api/oauth/callback/discord",
        "scope": "identify guilds",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            auth=aiohttp.BasicAuth(str(req.app.bot.user.id), CLIENT_SECRET),
        ) as response:
            response_data = await response.json()
            if response.status != 200:
                raise HTTPException(response.status, response_data)
            elif not all(x in response_data["scope"] for x in ("identify", "guilds")):
                log.warning(f"User authenticated with {response_data['scope']!r} scopes, not 'identify guilds'.")
                return RedirectResponse(req.url_for("discord_authorise", from_url=from_url))
        async with session.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {response_data['access_token']}"},
        ) as response:
            response_data["user"] = await response.json()
            user_data: discord.Member | None = await discord.utils.get_or_fetch(
                req.app.bot, "user", int(response_data["user"]["id"])
            )
            if not user_data:
                raise HTTPException(404, "User not found.")
            user = await DiscordOauthUser.get_or_none(id=user_data.id)
            exp = discord.utils.utcnow() + datetime.timedelta(seconds=response_data["expires_in"])
            token = jwt.encode(
                {"sub": user_data.id, "exp": exp},
                SECRET_KEY,
                algorithm=ALGORITHM,
            )
            if not user:
                user = DiscordOauthUser(
                    id=user_data.id,
                    access_token=response_data["access_token"],
                    refresh_token=response_data["refresh_token"],
                    expires_at=response_data["expires_in"],
                    session=token,
                )
            else:
                user.access_token = response_data["access_token"]
                user.refresh_token = response_data["refresh_token"]
                user.expires_at = response_data["expires_in"]
                user.session = token
            await user.save()
            if not to:
                to = f"{str(req.base_url)}?token={user.session}"
            response = RedirectResponse(url=to, status_code=303)
            response.set_cookie("_token", user.session, max_age=ACCESS_TOKEN_EXPIRE_SECONDS)
            response.delete_cookie("_state")
            return response
