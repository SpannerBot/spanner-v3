import datetime
import hashlib
import json
import typing
from typing import Annotated

import discord.utils
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status, Body
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response

from spanner.bot import CustomBridgeBot, bot as __bot
from spanner.share.database import (
    DiscordOauthUser,
    GuildAuditLogEntry,
    GuildAuditLogEntryPydantic,
    GuildConfig,
    GuildConfigPydantic,
    GuildLogFeatures,
    GuildLogFeaturesPydantic,
    GuildNickNameModeration,
    GuildNickNameModerationPydantic,
)

from ..models.config import GuildAuditLogEntryResponse, NicknameModerationUpdateBody
from .oauth2 import is_logged_in


class _FeatureToggle(BaseModel):
    enabled: bool


def _bot_is_ready_callback() -> CustomBridgeBot:
    if not __bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")
    return __bot


bot_is_ready = Depends(_bot_is_ready_callback)


router = APIRouter(tags=["Configuration"])


@router.get("/{guild_id}/presence", status_code=status.HTTP_204_NO_CONTENT)
async def get_guild_presence(guild_id: int, bot: Annotated[CustomBridgeBot, bot_is_ready]):
    """Checks that the bot is in the target server."""
    if not bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is not ready.")

    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guild_id}/nickname-moderation")
async def get_nickname_moderation(
    guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], bot: Annotated[CustomBridgeBot, bot_is_ready]
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


@router.patch("/{guild_id}/nickname-moderation")
async def set_nickname_moderation(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    bot: Annotated[CustomBridgeBot, bot_is_ready],
    hate: Annotated[bool | None, Body()] = None,
    harassment: Annotated[bool | None, Body()] = None,
    self_harm: Annotated[bool | None, Body()] = None,
    sexual: Annotated[bool | None, Body()] = None,
    violence: Annotated[bool | None, Body()] = None,
):
    """
    Update the nickname moderation configuration for the given guild.

    This will return the updated configuration. Omitted fields will not be changed.
    """
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")

    config, _ = await GuildNickNameModeration.get_or_create(guild_id=guild_id)

    if hate is not None:
        config.hate = hate
    if harassment is not None:
        config.harassment = harassment
    if self_harm is not None:
        config.self_harm = self_harm
    if sexual is not None:
        config.sexual = sexual
    if violence is not None:
        config.violence = violence
    await config.save()
    return await GuildNickNameModerationPydantic.from_tortoise_orm(config)


@router.delete("/{guild_id}/nickname-moderation", status_code=status.HTTP_204_NO_CONTENT)
async def disable_nickname_moderation(
    guild_id: int, user: Annotated[DiscordOauthUser, is_logged_in], bot: Annotated[CustomBridgeBot, bot_is_ready]
):
    """
    Disables nickname moderation for the guild, destroying the configuration.
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
    await config.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guild_id}/logging/channel")
async def get_log_channel(guild_id: int) -> str | None:
    """Fetches the current log channel, returning the channel ID as a snowflake"""
    config = await GuildConfig.get_or_none(id=guild_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild configuration not found.")
    return str(config.log_channel) if config.log_channel else None


@router.get("/{guild_id}/logging/features/enabled")
async def get_logging_features(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    bot: Annotated[CustomBridgeBot, bot_is_ready],
    enabled: bool | None = Query(
        None, description="Whether to only return enabled/disabled (true/false) features. None returns all."
    ),
) -> list[GuildLogFeaturesPydantic]:
    """
    Get the logging features configuration for the given guild.
    """
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")

    config = await GuildConfig.get_or_none(id=guild_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild configuration not found.")
    features = GuildLogFeatures.filter(guild=config)
    if enabled is not None:
        features = features.filter(enabled=enabled)
    return await GuildLogFeaturesPydantic.from_queryset(features.all())


@router.get("/{guild_id}/logging/features/all")
def get_all_log_features(res: JSONResponse, guild_id: int, if_none_match: str | None = Header(None)) -> list[str]:
    """
    Gets all available log features for the given server.

    Currently, this is a hardcoded list of features, and does not actually depend on the specific server.

    The etag returned by this endpoint is an md5 hash of the ordered comma-delimited array joined.
    Aka, md5(array.join(","))
    """
    etag = hashlib.md5(",".join(GuildLogFeatures.VALID_LOG_FEATURES).encode()).hexdigest()
    if if_none_match and if_none_match.strip('"') == etag:
        # noinspection PyTypeChecker
        # return Response(None, status.HTTP_304_NOT_MODIFIED)
        raise HTTPException(status.HTTP_304_NOT_MODIFIED, None)

    res.headers["etag"] = f'"{etag}"'
    return GuildLogFeatures.VALID_LOG_FEATURES


@router.put("/{guild_id}/logging/features/{feature}")
async def set_log_feature(
        guild_id: int,
        feature: str,
        body: _FeatureToggle,
        user: Annotated[DiscordOauthUser, is_logged_in],
        bot: Annotated[CustomBridgeBot, bot_is_ready]
):
    """
    Enable or disable a specific logging feature for the given guild.

    The body for this request should be a JSON object with a single key, `enabled`, which is a boolean.

    Tip: sending `DELETE .../logging/features/<feature>` is equivalent to sending `{"enabled": false}`.
    """
    if feature not in GuildLogFeatures.VALID_LOG_FEATURES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid feature.")
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")
    config = await GuildConfig.get_or_none(id=guild_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild configuration not found.")
    feature, _ = await GuildLogFeatures.get_or_create(guild=config, name=feature)
    feature.enabled = body.enabled
    await feature.save()
    return await GuildLogFeaturesPydantic.from_tortoise_orm(feature)


@router.delete("/{guild_id}/logging/features/{feature}")
async def delete_log_feature(
    guild_id: int,
    feature: str,
    user: Annotated[DiscordOauthUser, is_logged_in],
    bot: Annotated[CustomBridgeBot, bot_is_ready],
):
    """
    Disable a specific logging feature for the given guild.
    """

    if feature not in GuildLogFeatures.VALID_LOG_FEATURES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid feature.")

    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")

    config = await GuildConfig.get_or_none(id=guild_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild configuration not found.")
    feature = await GuildLogFeatures.get_or_none(guild=config, name=feature)
    if not feature:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Feature not found.")
    await feature.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guild_id}/audit-log")
async def get_guild_audit_logs(
    guild_id: int,
    user: Annotated[DiscordOauthUser, is_logged_in],
    bot: Annotated[CustomBridgeBot, bot_is_ready],
    before: datetime.datetime | None = Query(None),
    after: datetime.datetime | None = Query(None),
    limit: int = Query(100, le=100, ge=1),
    offset: int = Query(0, ge=0),
    author: int | None = Query(None),
    namespace: str | None = Query(None),
    action: str | None = Query(None),
) -> GuildAuditLogEntryResponse:
    """
    Get the audit logs for the given guild.

    "Audit Logs" in this context are meta, meaning related to the bot. Events such as configuration changes are logged
    here, not actual discord logs.

    * If `before` is specified, only entries created BEFORE this time are included.
    * If `after` is specified, only entries created AFTER this time are included.
    * If `limit` is specified, UP TO this many entries will be returned.
    * `Offset` must be specified to properly paginate. It may not be required if less than LIMIT entries are returned.
    * If `author` is specified, only entries created by the given user ID will be returned.
    * If `namespace` is specified, only entries for this specific namespace (e.g. `settings.logging.features`)
    will be returned.
    * If `action` is specified, only entries using this specific action (e.g. `toggle`) are returned.

    If any of these are omitted or nullified, excluding `offset` (default 0), and `limit` (default 100)
    filtering will not be performed on them.

    You can set author to `0` to automatically fill in the current authenticated user's ID, or 1 for the current bot's
    user ID.
    """
    if before and after and before >= after:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Before must be a time predating after")
    elif after and after > discord.utils.utcnow():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "After must be a time in the past, I cannot predict the future."
        )
    elif before and before.timestamp() < 1715026768:  # spanner creation timestamp
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Before time predates spanner's existence.")
    if author == 0:
        author = user.user_id
    elif author == 1:
        author = bot.user.id
    elif author and author > discord.utils.generate_snowflake():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Author snowflake does not exist yet.")

    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild not found.")

    member = await discord.utils.get_or_fetch(guild, "member", user.user_id)
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You are not in this guild.")
    elif not member.guild_permissions.manage_guild:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have the required permissions.")

    config = await GuildConfig.get_or_none(id=guild_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Guild configuration not found.")
    query = GuildAuditLogEntry.filter(guild_id=guild_id)
    if before is not None:
        query = query.filter(created_at__lt=before)
    if after is not None:
        query = query.filter(created_at__gt=after)
    if author is not None:
        query = query.filter(author=author)
    if namespace is not None:
        query = query.filter(namespace=namespace)
    if action is not None:
        query = query.filter(action=action)

    count = await query.all().count()
    query = query.order_by("-created_at").limit(limit).offset(offset)
    return GuildAuditLogEntryResponse(
        total=count, offset=offset, entries=await GuildAuditLogEntryPydantic.from_queryset(query)
    )
