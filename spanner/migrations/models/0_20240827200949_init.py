from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "discordoauthuser" (
    "guid" CHAR(36) NOT NULL  PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "access_token" VARCHAR(255) NOT NULL,
    "refresh_token" VARCHAR(255) NOT NULL,
    "expires_at" REAL NOT NULL,
    "session" VARCHAR(1024),
    "scope" TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_discordoaut_user_id_692ef0" ON "discordoauthuser" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_discordoaut_access__31a65c" ON "discordoauthuser" ("access_token");
CREATE TABLE IF NOT EXISTS "guildconfig" (
    "id" BIGINT NOT NULL  PRIMARY KEY,
    "log_channel" BIGINT
);
CREATE TABLE IF NOT EXISTS "autorole" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "role_id" BIGINT NOT NULL UNIQUE,
    "guild_id" BIGINT NOT NULL REFERENCES "guildconfig" ("id") ON DELETE CASCADE
) /* Roles to automatically grant new members */;
CREATE TABLE IF NOT EXISTS "guildauditlogentry" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "author" BIGINT NOT NULL,
    "namespace" VARCHAR(128) NOT NULL,
    "action" VARCHAR(128) NOT NULL,
    "description" TEXT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "guild_id" BIGINT NOT NULL REFERENCES "guildconfig" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "guildlogfeatures" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "name" VARCHAR(32) NOT NULL,
    "enabled" INT NOT NULL  DEFAULT 1,
    "updated" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "guild_id" BIGINT NOT NULL REFERENCES "guildconfig" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_guildlogfea_name_61cacc" ON "guildlogfeatures" ("name");
CREATE TABLE IF NOT EXISTS "guildnicknamemoderation" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "hate" INT NOT NULL  DEFAULT 0,
    "harassment" INT NOT NULL  DEFAULT 0,
    "self_harm" INT NOT NULL  DEFAULT 0,
    "sexual" INT NOT NULL  DEFAULT 0,
    "violence" INT NOT NULL  DEFAULT 0,
    "guild_id" BIGINT NOT NULL REFERENCES "guildconfig" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "premium" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "guild_id" BIGINT NOT NULL UNIQUE,
    "start" TIMESTAMP NOT NULL,
    "end" TIMESTAMP NOT NULL,
    "is_trial" INT NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_premium_guild_i_0f3bf9" ON "premium" ("guild_id");
CREATE TABLE IF NOT EXISTS "selfrolemenu" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "name" VARCHAR(32) NOT NULL,
    "channel" BIGINT NOT NULL,
    "message" BIGINT NOT NULL,
    "mode" SMALLINT NOT NULL,
    "roles" JSON NOT NULL,
    "maximum" SMALLINT NOT NULL  DEFAULT 25,
    "guild_id" BIGINT NOT NULL REFERENCES "guildconfig" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "starboardconfig" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "channel_id" BIGINT NOT NULL UNIQUE,
    "minimum_stars" SMALLINT NOT NULL  DEFAULT 1,
    "star_mode" SMALLINT NOT NULL  DEFAULT 0 /* COUNT: 0\nPERCENT: 1 */,
    "allow_self_star" INT NOT NULL  DEFAULT 0,
    "mirror_edits" INT NOT NULL  DEFAULT 0,
    "mirror_deletes" INT NOT NULL  DEFAULT 0,
    "allow_bot_messages" INT NOT NULL  DEFAULT 1,
    "star_emoji" VARCHAR(64) NOT NULL  DEFAULT '⭐',
    "guild_id" BIGINT NOT NULL REFERENCES "guildconfig" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "starboardentry" (
    "id" CHAR(36) NOT NULL  PRIMARY KEY,
    "source_message_id" BIGINT NOT NULL,
    "starboard_message_id" BIGINT NOT NULL,
    "source_channel_id" BIGINT NOT NULL,
    "config_id" CHAR(36) NOT NULL REFERENCES "starboardconfig" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
