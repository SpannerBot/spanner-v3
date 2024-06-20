import secrets
import typing

from tortoise import fields
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.models import Model


class GuildConfig(Model):
    id = fields.BigIntField(pk=True, generated=False)
    log_channel = fields.BigIntField(default=None, null=True)
    membership_log_channel = fields.BigIntField(default=None, null=True)

    if typing.TYPE_CHECKING:
        log_features: fields.ReverseRelation["GuildLogFeatures"]
        audit_log_entries: fields.ReverseRelation["GuildAuditLogEntry"]
        user_history: fields.ReverseRelation["UserHistory"]
        self_roles: fields.ReverseRelation["SelfRoleMenu"]


GuildConfigPydantic = pydantic_model_creator(GuildConfig, name="GuildConfig")


class GuildLogFeatures(Model):
    _VALID_LOG_FEATURES = [
        "message.edit",
        "message.delete.bulk",
        "message.delete",
        "member.join",
        "member.leave",
        "member.kick",
        "member.ban",
        "member.timeout",
        "member.unban",
        "member.nickname-change",
        "member.roles.add",
        "member.roles.remove",
    ]
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation["GuildConfig"] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="log_features"
    )

    name = fields.CharField(min_length=1, max_length=32, index=True)
    enabled = fields.BooleanField(default=True)
    updated = fields.DatetimeField(auto_now=True)


GuildLogFeaturesPydantic = pydantic_model_creator(GuildLogFeatures, name="GuildLogFeatures")


class GuildAuditLogEntry(Model):
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="audit_log_entries"
    )
    author = fields.BigIntField()
    namespace = fields.CharField(min_length=1, max_length=128)
    action = fields.CharField(min_length=1, max_length=128)
    description = fields.TextField()
    created_at = fields.DatetimeField(auto_now=True)


GuildAuditLogEntryPydantic = pydantic_model_creator(GuildAuditLogEntry, name="GuildAuditLogEntry")


class UserHistory(Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.BigIntField()
    username = fields.CharField(min_length=2, max_length=32)
    nickname = fields.CharField(min_length=1, max_length=32, default=None, null=True)
    avatar_hash = fields.CharField(max_length=255, default=None, null=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="user_history"
    )


UserHistoryPydantic = pydantic_model_creator(UserHistory, name="UserHistory")


class SelfRoleMenu(Model):
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="self_roles"
    )
    name = fields.CharField(min_length=1, max_length=32)
    channel = fields.BigIntField()
    message = fields.BigIntField()
    mode = fields.SmallIntField()
    roles = fields.JSONField(default=[])
    # minimum = fields.SmallIntField(default=0)
    maximum = fields.SmallIntField(default=25)


SelfRoleMenuPydantic = pydantic_model_creator(SelfRoleMenu, name="SelfRoleMenu")


class PremiumKey(Model):
    id = fields.UUIDField(pk=True)
    key = fields.CharField(min_length=8, max_length=512, unique=True, default=secrets.token_hex)
    created_at = fields.DatetimeField(auto_now=True)
    redeemed_at = fields.DatetimeField(null=True)
    redeemer = fields.BigIntField(null=True)


PremiumKeyPydantic = pydantic_model_creator(PremiumKey, name="PremiumKey")


class PremiumGuild(Model):
    id = fields.UUIDField(pk=True)
    guild_id = fields.BigIntField()
    premium_since = fields.FloatField()
    premium_until = fields.FloatField(null=True)


PremiumGuildPydantic = pydantic_model_creator(PremiumGuild, name="PremiumGuild")


class DiscordOauthUser(Model):
    id = fields.BigIntField(pk=True, generated=False)
    access_token = fields.CharField(max_length=255)
    refresh_token = fields.CharField(max_length=255)
    expires_at = fields.FloatField()
    session = fields.CharField(max_length=1024, default=None, null=True)
