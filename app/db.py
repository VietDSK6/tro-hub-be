from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .settings import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

async def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        _db = _client[settings.mongodb_db]
    return _db

async def close_db():
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
