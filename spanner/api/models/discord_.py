from typing import Annotated, Literal

from pydantic import BaseModel, computed_field, HttpUrl


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

    @computed_field
    @property
    def avatar_url(self) -> Annotated[HttpUrl, str]:
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
    owner: bool

    @computed_field
    @property
    def icon_url(self) -> Annotated[HttpUrl, str]:
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
