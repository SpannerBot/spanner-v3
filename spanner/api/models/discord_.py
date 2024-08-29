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
    def from_user(cls, user: discord.User):
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


class BasicChannelInformation(BaseModel):
    id: str
    type: int
    name: str
    user_permissions: str | None = None
    bot_permissions: str
    flags: int = 0
