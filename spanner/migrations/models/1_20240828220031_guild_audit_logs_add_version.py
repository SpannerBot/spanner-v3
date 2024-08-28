from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "guildauditlogentry" ADD "metadata" JSON NOT NULL DEFAULT '{}';
        ALTER TABLE "guildauditlogentry" ADD "version" INT NOT NULL DEFAULT 2;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "guildauditlogentry" DROP COLUMN "metadata";    
        ALTER TABLE "guildauditlogentry" DROP COLUMN "version";"""
