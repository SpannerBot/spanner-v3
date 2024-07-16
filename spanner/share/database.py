import enum
import secrets
import typing

from tortoise import fields
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.models import Model


class GuildConfig(Model):
    id = fields.BigIntField(pk=True, generated=False)
    log_channel = fields.BigIntField(default=None, null=True)

    def __repr__(self):
        return "GuildConfig(id={0.id!r}, log_channel={0.log_channel!r})".format(self)

    if typing.TYPE_CHECKING:
        log_features: fields.ReverseRelation["GuildLogFeatures"]
        audit_log_entries: fields.ReverseRelation["GuildAuditLogEntry"]
        user_history: fields.ReverseRelation["UserHistory"]
        self_roles: fields.ReverseRelation["SelfRoleMenu"]
        nickname_moderation: fields.ReverseRelation["GuildNickNameModeration"]
        starboard: fields.ReverseRelation["StarboardConfig"]


GuildConfigPydantic = pydantic_model_creator(GuildConfig, name="GuildConfig")


class GuildNickNameModeration(Model):
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation["GuildConfig"] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="nickname_moderation", on_delete=fields.CASCADE
    )
    hate = fields.BooleanField(default=False)
    harassment = fields.BooleanField(default=False)
    self_harm = fields.BooleanField(default=False)
    sexual = fields.BooleanField(default=False)
    violence = fields.BooleanField(default=False)

    CATEGORIES = {
        "hate": "Content that expresses, incites, or promotes hate based on protected characteristics.",
        "harassment": "Content that expresses, incites, or promotes harassing language towards any target.",
        "self_harm": "Content that promotes, encourages, or depicts acts of self-harm.",
        "sexual": "Content meant to arouse, such as the description of sexual activity, or that promotes sex services.",
        "violence": "Content that depicts death, violence, or physical injury.",
    }


GuildNickNameModerationPydantic = pydantic_model_creator(GuildNickNameModeration, name="GuildNickNameModeration")


class GuildLogFeatures(Model):
    VALID_LOG_FEATURES = [
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
        "member.avatar-change",
        "member.roles.update",
        "server.role.create",
        "server.role.edit",
        "server.role.permissions.edit",
        "server.role.delete",
        "server.invite.create",
        "server.invite.delete",
        "server.channel.create",
        "server.channel.delete",
    ]
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation["GuildConfig"] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="log_features", on_delete=fields.CASCADE
    )

    name = fields.CharField(min_length=1, max_length=32, index=True)
    enabled = fields.BooleanField(default=True)
    updated = fields.DatetimeField(auto_now=True)


GuildLogFeaturesPydantic = pydantic_model_creator(GuildLogFeatures, name="GuildLogFeatures")


class GuildAuditLogEntry(Model):
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="audit_log_entries", on_delete=fields.CASCADE
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
        "models.GuildConfig", related_name="user_history", on_delete=fields.CASCADE
    )


UserHistoryPydantic = pydantic_model_creator(UserHistory, name="UserHistory")


class SelfRoleMenu(Model):
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="self_roles", on_delete=fields.CASCADE
    )
    name = fields.CharField(min_length=1, max_length=32)
    channel = fields.BigIntField()
    message = fields.BigIntField()
    mode = fields.SmallIntField()
    roles = fields.JSONField(default=[])
    maximum = fields.SmallIntField(default=25)

    def __repr__(self):
        return (
            "SelfRoleMenu(id={0.id!r}, guild={0.guild!r}, name={0.name!r}, channel={0.channel!r}, message={0.message!r}"
            ", mode={0.mode!r}, roles={0.roles!r}, maximum={0.maximum!r})".format(self)
        )


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


class StarboardMode(enum.IntEnum):
    COUNT = 0
    """Up to N stars are required to be on the starboard."""
    PERCENT = 1
    """Up to N% of the current channel's members must've starred the message."""


class StarboardConfig(Model):
    id = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="starboard", on_delete=fields.CASCADE
    )
    channel_id = fields.BigIntField(unique=True)
    minimum_stars = fields.SmallIntField(default=1)
    star_mode = fields.IntEnumField(StarboardMode, default=StarboardMode.COUNT)
    allow_self_star = fields.BooleanField(default=False)
    mirror_edits = fields.BooleanField(default=False)
    mirror_deletes = fields.BooleanField(default=False)
    allow_bot_messages = fields.BooleanField(default=True)
    star_emoji = fields.CharField(max_length=64, default="\N{WHITE MEDIUM STAR}")


StarboardConfigPydantic = pydantic_model_creator(StarboardConfig, name="StarboardConfig")


class StarboardEntry(Model):
    id = fields.UUIDField(pk=True)
    source_message_id = fields.BigIntField()
    starboard_message_id = fields.BigIntField()
    source_channel_id = fields.BigIntField()
    config: fields.ForeignKeyRelation[StarboardConfig] = fields.ForeignKeyField(
        "models.StarboardConfig", related_name="entries", on_delete=fields.CASCADE
    )


StarboardEntryPydantic = pydantic_model_creator(StarboardEntry, name="StarboardEntry")
