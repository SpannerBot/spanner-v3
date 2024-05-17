from enum import Enum

import discord

__all__ = [
    "verification_levels",
    "content_filters",
    "content_filter_names",
    "nsfw_levels",
    "boolean_emojis",
    "status_circles",
]


verification_levels: dict[discord.VerificationLevel, str] = {
    discord.VerificationLevel.none: "Unrestricted",
    discord.VerificationLevel.low: "Must have a verified email",
    discord.VerificationLevel.medium: "Must be registered on Discord for longer than 5 minutes & "
    "must have a verified email",
    discord.VerificationLevel.high: "Must be a member of the server for longer than 10 minutes, "
    "must be registered on discord for longer than 5 minutes, and must have a "
    "verified email",
    discord.VerificationLevel.highest: "Must have a verified phone number",
}

content_filters: dict[discord.ContentFilter, str] = {
    discord.ContentFilter.disabled: "No messages are filtered",
    discord.ContentFilter.no_role: "Recommended for servers who use roles for trusted membership",
    discord.ContentFilter.all_members: "Recommended for when you want that squeaky clean shine",
}

content_filter_names: dict[discord.ContentFilter, str] = {
    discord.ContentFilter.disabled: "Don't scan any media content",
    discord.ContentFilter.no_role: "Scan media content from members without a role",
    discord.ContentFilter.all_members: "Scan media content from all members",
}

nsfw_levels: dict[discord.NSFWLevel, str] = {
    discord.NSFWLevel.default: "Uncategorized",
    discord.NSFWLevel.explicit: "Guild contains NSFW content",
    discord.NSFWLevel.safe: "Guild does not contain NSFW content",
    discord.NSFWLevel.age_restricted: "Guild *may* contain NSFW content",
}

boolean_emojis: dict[bool, str] = {
    True: "\N{white heavy check mark}",
    False: "\N{cross mark}",
}

status_circles: dict[str, str] = {
    "success": "\U0001f7e2",
    "warning": "\U0001f7e1",
    "error": "\U0001f534",
    "disabled": "\u26AB",
}
