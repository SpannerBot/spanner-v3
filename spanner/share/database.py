import datetime
import enum
import json
import typing
import uuid
import warnings
from typing import Any, Union

import discord
from tortoise import fields
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.models import Model

try:
    import aerich.models
except ImportError:
    raise RuntimeError("Aerich is not installed. Please install it by running `pip install aerich`.")


class GuildConfig(Model):
    id: int = fields.BigIntField(pk=True, generated=False)
    log_channel: int | None = fields.BigIntField(default=None, null=True)

    def __repr__(self):
        return "GuildConfig(id={0.id!r}, log_channel={0.log_channel!r})".format(self)

    if typing.TYPE_CHECKING:
        log_features: fields.ReverseRelation["GuildLogFeatures"]
        audit_log_entries: fields.ReverseRelation["GuildAuditLogEntry"]
        self_roles: fields.ReverseRelation["SelfRoleMenu"]
        nickname_moderation: fields.ReverseRelation["GuildNickNameModeration"]
        starboard: fields.ReverseRelation["StarboardConfig"]


GuildConfigPydantic = pydantic_model_creator(GuildConfig, name="GuildConfig")


class GuildNickNameModeration(Model):
    id: uuid.UUID = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation["GuildConfig"] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="nickname_moderation", on_delete=fields.CASCADE
    )
    hate: bool = fields.BooleanField(default=False)
    """Content that expresses, incites, or promotes hate based on protected characteristics."""
    harassment: bool = fields.BooleanField(default=False)
    """Content that expresses, incites, or promotes harassing language towards any target."""
    self_harm: bool = fields.BooleanField(default=False)
    """Content that promotes, encourages, or depicts acts of self-harm."""
    sexual: bool = fields.BooleanField(default=False)
    """Content meant to arouse, such as the description of sexual activity, or that promotes sex services."""
    violence: bool = fields.BooleanField(default=False)
    """Content that depicts death, violence, or physical injury."""

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
    id: uuid.UUID = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation["GuildConfig"] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="log_features", on_delete=fields.CASCADE
    )

    name: str = fields.CharField(min_length=1, max_length=32, index=True)
    enabled: bool = fields.BooleanField(default=True)
    updated: datetime.datetime = fields.DatetimeField(auto_now=True)


GuildLogFeaturesPydantic = pydantic_model_creator(GuildLogFeatures, name="GuildLogFeatures")
TargetTypes = Union[
    discord.Member,
    discord.User,
    discord.Role,
    discord.Guild,
    discord.TextChannel,
    discord.VoiceChannel,
    discord.CategoryChannel,
    discord.Invite,
    discord.Message,
    discord.Emoji,
    discord.PartialEmoji,
    discord.abc.Snowflake,
    Any,
]


class GuildAuditLogEntry(Model):
    id: uuid.UUID = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="audit_log_entries", on_delete=fields.CASCADE
    )
    author: int = fields.BigIntField()
    namespace: str = fields.CharField(min_length=1, max_length=128)
    action: str = fields.CharField(min_length=1, max_length=128)
    description: str = fields.TextField()
    created_at: datetime.datetime = fields.DatetimeField(auto_now=True)
    metadata: dict = fields.JSONField(default={})
    version: int = fields.IntField(default=2)

    @classmethod
    async def generate(
        cls,
        guild_id: int,
        author: discord.User | discord.Member | discord.abc.Snowflake | int,
        namespace: str,
        action: str,
        description: str,
        metadata: dict | None = None,
        *,
        target: Any = None,
        using_db=None,
    ) -> typing.Self:
        """
        Generates a new audit log entry

        This function should be used instead of create(), as it produces a consistent, API-friendly output.
        """
        metadata = metadata or {}
        if isinstance(author, int):
            author = discord.Object(id=author)
        metadata.setdefault("author", {})
        metadata["author"]["id"] = str(author.id)
        if isinstance(author, (discord.User, discord.ClientUser, discord.Member)):
            metadata["author"]["nick"] = author.nick
            metadata["author"]["username"] = author.name
            metadata["author"]["display_name"] = author.display_name
            metadata["author"]["avatar_url"] = author.display_avatar.url
            metadata["author"]["color"] = author.color.value
            metadata["author"]["flags"] = author.public_flags.value

        if "action.historical" not in metadata:
            warnings.warn(
                "The 'action.historical' key is not present in the metadata."
                "This may cause issues with historical data.",
                RuntimeWarning,
                stacklevel=2,
            )
            match action:
                case "add":
                    metadata["action.historical"] = "added"
                case "remove":
                    metadata["action.historical"] = "removed"
                case "update":
                    metadata["action.historical"] = "updated"
                case "modify":
                    metadata["action.historical"] = "modified"
                case "create":
                    metadata["action.historical"] = "created"
                case "delete":
                    metadata["action.historical"] = "deleted"

        if target:
            match type(target):
                case discord.Member:
                    from spanner.api.models.discord_ import Member

                    metadata["target"] = Member.from_member(target).model_dump()
                case discord.User:
                    from spanner.api.models.discord_ import User

                    metadata["target"] = User.from_user(target).model_dump()
                case discord.Guild:
                    from spanner.api.models.discord_ import PartialGuild

                    metadata["target"] = PartialGuild.from_guild(target).model_dump()
                case discord.Role:
                    from spanner.api.models.discord_ import Role

                    metadata["target"] = Role.from_role(target).model_dump()
                case discord.TextChannel:
                    from spanner.api.models.discord_ import ChannelInformation

                    metadata["target"] = ChannelInformation.from_channel(target).model_dump()
                case discord.VoiceChannel:
                    from spanner.api.models.discord_ import ChannelInformation

                    metadata["target"] = ChannelInformation.from_channel(target).model_dump()
                case discord.StageChannel:
                    from spanner.api.models.discord_ import ChannelInformation

                    metadata["target"] = ChannelInformation.from_channel(target).model_dump()
                case discord.CategoryChannel:
                    from spanner.api.models.discord_ import ChannelInformation

                    metadata["target"] = ChannelInformation.from_channel(target).model_dump()
                case discord.abc.Snowflake:
                    metadata["target"] = {"id": str(target.id)}
                case _:
                    try:
                        metadata["target"] = json.loads(
                            json.dumps(getattr(target, "to_dict", lambda: target)(), default=repr)
                        )
                    except Exception as e:
                        metadata["target"] = repr(target)
                        warnings.warn(f"Failed to convert target to JSON: {e!r}", RuntimeWarning, stacklevel=2)

        return await cls.create(
            guild_id=guild_id,
            author=str(author.id),
            namespace=namespace,
            action=action,
            description=description,
            metadata=metadata,
            version=4 if target else 3,
            using_db=using_db,
        )


GuildAuditLogEntryPydantic = pydantic_model_creator(GuildAuditLogEntry, name="GuildAuditLogEntry")


class SelfRoleMenu(Model):
    id: uuid.UUID = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="self_roles", on_delete=fields.CASCADE
    )
    name: str = fields.CharField(min_length=1, max_length=32)
    channel: int = fields.BigIntField()
    message: int = fields.BigIntField()
    mode: int = fields.SmallIntField()
    roles: list = fields.JSONField(default=[])
    maximum: int = fields.SmallIntField(default=25)

    def __repr__(self):
        return (
            "SelfRoleMenu(id={0.id!r}, guild={0.guild!r}, name={0.name!r}, channel={0.channel!r}, message={0.message!r}"
            ", mode={0.mode!r}, roles={0.roles!r}, maximum={0.maximum!r})".format(self)
        )


SelfRoleMenuPydantic = pydantic_model_creator(SelfRoleMenu, name="SelfRoleMenu")


class DiscordOauthUser(Model):
    guid: uuid.UUID = fields.UUIDField(pk=True)
    user_id = fields.BigIntField(index=True)
    access_token = fields.CharField(max_length=255, index=True)
    refresh_token = fields.CharField(max_length=255)
    expires_at = fields.FloatField()
    session = fields.CharField(max_length=1024, default=None, null=True)
    scope: str = fields.TextField()


class StarboardMode(enum.IntEnum):
    COUNT = 0
    """Up to N stars are required to be on the starboard."""
    PERCENT = 1
    """Up to N% of the current channel's members must've starred the message."""


class StarboardConfig(Model):
    id: uuid.UUID = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="starboard", on_delete=fields.CASCADE
    )
    channel_id: int = fields.BigIntField(unique=True)
    minimum_stars: int = fields.SmallIntField(default=1)
    star_mode: StarboardMode = fields.IntEnumField(StarboardMode, default=StarboardMode.COUNT)
    allow_self_star: bool = fields.BooleanField(default=False)
    mirror_edits: bool = fields.BooleanField(default=False)
    mirror_deletes: bool = fields.BooleanField(default=False)
    allow_bot_messages: bool = fields.BooleanField(default=True)
    star_emoji: str = fields.CharField(max_length=64, default="\N{WHITE MEDIUM STAR}")


StarboardConfigPydantic = pydantic_model_creator(StarboardConfig, name="StarboardConfig")


class StarboardEntry(Model):
    id: uuid.UUID = fields.UUIDField(pk=True)
    source_message_id: int = fields.BigIntField()
    starboard_message_id: int = fields.BigIntField()
    source_channel_id: int = fields.BigIntField()
    config: fields.ForeignKeyRelation[StarboardConfig] = fields.ForeignKeyField(
        "models.StarboardConfig", related_name="entries", on_delete=fields.CASCADE
    )


StarboardEntryPydantic = pydantic_model_creator(StarboardEntry, name="StarboardEntry")


class Premium(Model):
    class Meta:
        table = "premium"

    id = fields.UUIDField(pk=True)
    user_id = fields.BigIntField()
    """The user ID the premium belongs to."""
    guild_id = fields.BigIntField(unique=True, index=True)
    """The guild ID the premium belongs to."""
    start = fields.DatetimeField(default=discord.utils.utcnow)
    """When the premium started"""
    end = fields.DatetimeField()
    """When the premium ends"""
    is_trial = fields.BooleanField()
    """Whether the premium is a trial (True) or official discord purchase (False)"""

    @property
    def is_expired(self) -> bool:
        return discord.utils.utcnow() >= self.end

    @is_expired.setter
    def is_expired(self, value: typing.Literal[True]) -> None:
        if value is not True:
            raise ValueError("Premium.is_expired can only be set to True.")
        self.end = discord.utils.utcnow()

    @classmethod
    async def from_entitlement(cls, entitlement: discord.Entitlement) -> "Premium":
        """
        Creates a premium entry from an entitlement.
        """
        existing = await cls.get_or_none(guild_id=entitlement.guild_id)
        if existing:
            existing.end = entitlement.ends_at
            existing.user_id = entitlement.user_id
            existing.is_trial = False
            await existing.save()
            return existing
        else:
            result = await cls.create(
                user_id=entitlement.user_id,
                guild_id=entitlement.guild_id,
                start=entitlement.starts_at,
                end=entitlement.ends_at,
                is_trial=False,
            )
            return result

    async def delete(self, *args) -> None:
        if self.is_trial:
            raise RuntimeError("Premium trial objects cannot be deleted.")
        await super().delete(*args)


class AutoRole(Model):
    """Roles to automatically grant new members"""

    id: uuid.UUID = fields.UUIDField(pk=True)
    guild: fields.ForeignKeyRelation[GuildConfig] = fields.ForeignKeyField(
        "models.GuildConfig", related_name="auto_roles", on_delete=fields.CASCADE
    )
    role_id: int = fields.BigIntField(unique=True)
