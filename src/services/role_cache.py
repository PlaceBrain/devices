from uuid import UUID

from redis.asyncio import Redis


class RoleCacheService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_role(self, user_id: UUID, place_id: UUID) -> str | None:
        role: str | None = await self.redis.hget(f"place_roles:{place_id}", str(user_id))
        return role

    async def set_role(self, place_id: UUID, user_id: UUID, role: str) -> None:
        await self.redis.hset(f"place_roles:{place_id}", str(user_id), role)
        await self.redis.sadd(f"user_places:{user_id}", str(place_id))

    async def remove_role(self, place_id: UUID, user_id: UUID) -> None:
        await self.redis.hdel(f"place_roles:{place_id}", str(user_id))
        await self.redis.srem(f"user_places:{user_id}", str(place_id))

    async def remove_place(self, place_id: UUID) -> None:
        members = await self.redis.hkeys(f"place_roles:{place_id}")
        for member in members:
            await self.redis.srem(f"user_places:{member}", str(place_id))
        await self.redis.delete(f"place_roles:{place_id}")

    async def get_user_places(self, user_id: UUID) -> set[str]:
        result: set[str] = await self.redis.smembers(f"user_places:{user_id}")
        return result
