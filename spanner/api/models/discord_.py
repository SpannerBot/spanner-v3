import datetime

import discord
from typing import Annotated, Literal

from pydantic import BaseModel, HttpUrl, computed_field


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    refresh_token: str
    scope: str

    @property
    def scope_array(self) -> list[str]:
        return self.scope.split()


class User(BaseModel):
    id: str
    username: str
    discriminator: str
    global_name: str | None
    avatar: str | None
    bot: bool | None = None
    system: bool | None = None
    mfa_enabled: bool | None = None
    banner: str | None
    accent_color: int | None
    locale: str | None
    flags: int | None
    premium_type: int | None
    public_flags: int | None

    @classmethod
    def from_user(cls, user: discord.User | discord.Member):
        """Creates a User object from a discord.User object."""
        return cls(
            id=str(user.id),
            username=user.name,
            discriminator=user.discriminator,
            global_name=user.global_name,
            avatar=user.avatar.key if user.avatar else None,
            bot=user.bot,
            system=user.system,
            banner=user.banner.key if user.banner else None,
            flags=user.public_flags.value,
            public_flags=user.public_flags.value,
            accent_color=user.accent_color.value if user.accent_color else None,
            locale=None,
            premium_type=None
        )

    @computed_field
    @property
    def avatar_url(self) -> str:
        """Calculates the avatar URL for the user."""
        if self.avatar is None:
            return f"https://cdn.discordapp.com/embed/avatars/{(int(self.id) >> 22) % 6}.png?size=512"
        return "https://cdn.discordapp.com/avatars/{0.id!s}/{0.avatar}.webp?size=512".format(self)


class PartialGuild(BaseModel):
    id: str
    name: str
    icon: str | None = None
    owner: bool | None = None
    permissions: str | None = None
    features: list[str] = None
    owner: bool | None
    
    @classmethod
    def from_member(cls, member: discord.Member):
        """Creates a PartialGuild object from a discord.Member object."""
        guild: discord.Guild = member.guild
        return cls(
            id=str(guild.id),
            name=guild.name,
            icon=guild.icon.key if guild.icon else None,
            owner=guild.owner_id == member.id,
            permissions=str(member.guild_permissions.value),
            features=guild.features,
        )
    
    @classmethod
    def from_guild(cls, guild: discord.Guild):
        """Creates a PartialGuild object from a discord.Guild object."""
        return cls(
            id=str(guild.id),
            name=guild.name,
            icon=guild.icon.key if guild.icon else None,
            features=guild.features,
            owner=None
        )

    @computed_field
    @property
    def icon_url(self) -> str:
        """Calculates the icon URL for the guild."""
        if self.icon is None:
            return f"https://cdn.discordapp.com/embed/avatars/{(int(self.id) >> 22) % 6}.png?size=512"
        return "https://cdn.discordapp.com/icons/{0.id!s}/{0.icon}.webp?size=512".format(self)


class ChannelInformation(BaseModel):
    """
    Partially represents a discord channel.

    This model contains only data that is mutual between all channel types.
    """
    id: str
    type: int
    guild_id: str | None = None
    position: int = 0
    name: str
    topic: str | None = None
    nsfw: bool = False

    user_permissions: str | None = None
    bot_permissions: str
    flags: int = 0

    @classmethod
    def from_channel(
            cls,
            channel: discord.abc.GuildChannel
    ):
        """Creates a BasicChannelInformation object from a discord.abc.GuildChannel object."""
        extra = {}
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            extra["topic"] = channel.topic
            extra["nsfw"] = channel.is_nsfw()
        return cls(
            id=str(channel.id),
            type=channel.type.value,
            guild_id=str(channel.guild.id),
            position=channel.position,
            name=channel.name,
            user_permissions=str(channel.permissions_for(channel.guild.me).value),
            bot_permissions=str(channel.permissions_for(channel.guild.me).value),
            flags=channel.flags.value,
            **extra
        )


class Member(BaseModel):
    user: User = {}
    nick: str | None = None
    avatar: str | None = None
    roles: list[str] = []
    joined_at: datetime.datetime
    premium_since: datetime.datetime | None = None
    deaf: bool
    mute: bool
    flags: int
    pending: bool = None
    permissions: str  = None
    communication_disabled_until: datetime.datetime | None = None
    _guild_id: str | None = None
    """This field is not part of the discord API and is only used to calculate the avatar URL."""

    @classmethod
    def from_member(cls, member: discord.Member):
        """Creates a Member object from a discord.Member object."""
        return cls(
            user=User.from_user(member),
            nick=member.nick,
            avatar=member.avatar.key if member.avatar else None,
            roles=[str(role.id) for role in member.roles],
            joined_at=member.joined_at,
            premium_since=member.premium_since,
            deaf=member.voice.deaf if member.voice else False,
            mute=member.voice.mute if member.voice else False,
            flags=member.public_flags.value,
            permissions=str(member.guild_permissions.value),
            communication_disabled_until=member.communication_disabled_until
        )

    @computed_field
    @property
    def avatar_url(self) -> str | None:
        """Calculates the icon URL for the member. May not be anything."""
        if not self.user:
            # No user - can't calculate avatar.
            return
        if self.avatar is None:
            # No guild-specific avatar. Fall back to user.
            return self.user.avatar_url

        uri = "/guilds/{0._guild_id}/users/{0.user.id}/avatars/{0.avatar}.webp?size=512"
        return "https://cdn.discordapp.com" + uri.format(self)
