import discord

__all__ = [
    "verification_levels",
    "content_filters",
    "content_filter_names",
    "nsfw_levels",
    "boolean_emojis",
    "status_circles",
    "public_flag_emojis",
    "platform_emojis",
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
    True: "\N{WHITE HEAVY CHECK MARK}",
    False: "\N{CROSS MARK}",
}

status_circles: dict[str, str] = {
    "success": "\U0001f7e2",
    "warning": "\U0001f7e1",
    "error": "\U0001f534",
    "disabled": "\u26ab",
}

public_flag_emojis = {
    "staff": "<:staff:729381672977432587>",
    "partner": "<:partner:729381698625863724>",
    "hypesquad": "<:HypeSquad:780079025032527903>",
    "bug_hunter": "<:bughunter:729381930113564712>",
    "bug_hunter_level_2": "<:bughunter:729381930113564712>",
    "hypesquad_bravery": "<:bravery:729381829056135209>",
    "hypesquad_brilliance": "<:brilliance:729381808269033739>",
    "hypesquad_balance": "<:balance:729381848639340544>",
    "early_supporter": "<:supporter:729381881543524364>",
    "verified_bot": "<:verifiedbot:729382007511187526>",
    "verified_bot_developer": "<:verifieddev:729383160021909574>",
    "early_verified_bot_developer": "<:verifieddev:729383160021909574>",
    "active_developer": "<:active_dev:1245059716904648837>",
}

platform_emojis = {
    "web": "<:browser:1245065854022844568>",
    "mobile": "\U0001f4f1",
    "desktop": "\U0001f5a5\U0000fe0f",
}
