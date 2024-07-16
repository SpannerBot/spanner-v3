import discord
from fastapi import APIRouter, HTTPException

from spanner.share.database import (
    GuildAuditLogEntry,
    GuildAuditLogEntryPydantic,
    GuildConfig,
    GuildConfigPydantic,
    GuildLogFeatures,
    GuildLogFeaturesPydantic,
    GuildNickNameModeration,
    GuildNickNameModerationPydantic,
    SelfRoleMenu,
    SelfRoleMenuPydantic,
    StarboardConfig,
    StarboardConfigPydantic,
    StarboardEntry,
    StarboardEntryPydantic,
)

from ..auth import user_has_permissions

api = APIRouter(prefix="/api/guilds", tags=["Guilds"])


@api.get("/{guild_id}/config", response_model=GuildConfigPydantic, dependencies=[user_has_permissions(0)])
async def get_guild_config(guild_id: int):
    """
    Fetches the config for a guild

    This information itself is not very useful.
    """

    config = await GuildConfig.get_or_none(guild_id=guild_id)
    if not config:
        raise HTTPException(404, "No config found.")

    return await GuildConfigPydantic.from_tortoise_orm(config)


@api.get(
    "/{guild_id}/config/nickname-moderation",
    response_model=GuildNickNameModerationPydantic,
    dependencies=[user_has_permissions(discord.Permissions(manage_nicknames=True))],
)
async def get_guild_nickname_config(guild_id: int):
    """
    Fetches the nickname moderation config for a guild.

    This is a list of categories that are enabled for AI nickname moderation.
    """

    config = await GuildNickNameModeration.get_or_none(guild__id=guild_id)
    if not config:
        raise HTTPException(404, "No nickname moderation config found.")

    return await GuildNickNameModerationPydantic.from_tortoise_orm(config)


@api.get(
    "/{guild_id}/config/log-features",
    response_model=list[GuildLogFeaturesPydantic],
    dependencies=[user_has_permissions(discord.Permissions(view_audit_log=True))],
)
async def get_guild_log_features(guild_id: int):
    """
    Fetches the log features for a guild.

    This is a list of log features that are enabled for a guild.
    """

    features = await GuildLogFeatures.filter(guild__id=guild_id)
    if not features:
        raise HTTPException(404, "No log features found.")

    return [await GuildLogFeaturesPydantic.from_tortoise_orm(feature) for feature in features]


@api.get("/{guild_id}/config/log-features/all", response_model=list[str])
def get_all_available_log_features():
    """
    Returns a list of all the available log flags.
    """
    return GuildLogFeatures.VALID_LOG_FEATURES


@api.get(
    "/{guild_id}/audit-logs",
    response_model=list[GuildAuditLogEntryPydantic],
    dependencies=[user_has_permissions(discord.Permissions(view_audit_log=True))],
)
async def get_audit_logs(guild_id: int):
    """
    Fetches the audit logs for a guild.

    This is an array of audit log entries, ordered newest->oldest.
    """
    audit_log = await GuildAuditLogEntry.filter(guild__id=guild_id).order_by("-created_at").all()
    if not audit_log:
        raise HTTPException(404, "No audit logs found.")

    return [await GuildAuditLogEntryPydantic.from_tortoise_orm(entry) for entry in audit_log]


# Section: SelfRoles ###


@api.get("/{guild_id}/self-roles", response_model=list[SelfRoleMenuPydantic], tags=["Guilds", "Self-Roles"])
async def get_guild_self_roles(guild_id: int):
    """
    Fetches the self roles for a guild.

    This is a list of self roles menus that are available for a guild.
    """
    roles = await SelfRoleMenu.filter(guild__id=guild_id)
    if not roles:
        raise HTTPException(404, "No self roles found.")

    return [await SelfRoleMenuPydantic.from_tortoise_orm(role) for role in roles]


@api.get("/{guild_id}/starboard/config", response_model=StarboardConfigPydantic, tags=["Guilds", "Starboard"])
async def get_starboard_config(guild_id: int):
    """
    Fetches the starboard config for a guild.

    This is a list of self roles menus that are available for a guild.
    """
    config = await StarboardConfig.get_or_none(guild__id=guild_id)
    if not config:
        raise HTTPException(404, "No starboard config found.")

    return await StarboardConfigPydantic.from_tortoise_orm(config)


@api.get("/{guild_id}/starboard/entries", response_model=list[StarboardEntryPydantic], tags=["Guilds", "Starboard"])
async def get_starboard_entries(guild_id: int):
    """
    Fetches the starboard entries for a guild.

    This is a list of starboard entries that are available for a guild.
    """
    entries = await StarboardEntry.filter(guild__id=guild_id)
    if not entries:
        raise HTTPException(404, "No starboard entries found.")

    return [await StarboardEntryPydantic.from_tortoise_orm(entry) for entry in entries]
