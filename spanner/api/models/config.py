from pydantic import BaseModel

from spanner.share.database import GuildAuditLogEntryPydantic

__all__ = ("GuildAuditLogEntryResponse", "NicknameModerationUpdateBody")


class GuildAuditLogEntryResponse(BaseModel):
    entries: list[GuildAuditLogEntryPydantic]
    """All of the found entries that matched the given criteria."""
    total: int
    """The total number of entries that matched the given query.
    
    This is not how many were returned, but how many you can get out of pagination."""
    offset: int = 0
    """The offset of the query."""


class NicknameModerationUpdateBody(BaseModel):
    hate: bool = None
    """Content that expresses, incites, or promotes hate based on protected characteristics."""
    harassment: bool = None
    """Content that expresses, incites, or promotes harassing language towards any target."""
    self_harm: bool = None
    """Content that promotes, encourages, or depicts acts of self-harm."""
    sexual: bool = None
    """Content meant to arouse, such as the description of sexual activity, or that promotes sex services."""
    violence: bool = None
    """Content that depicts death, violence, or physical injury."""
