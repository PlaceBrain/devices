from uuid import UUID

from redis.asyncio import Redis


class RoleCacheService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_role(self, user_id: UUID, place_id: UUID) -> str | None:
        role = await self.redis.hget(f"place_roles:{place_id}", str(user_id))
        if isinstance(role, bytes):
            return role.decode()
        return role

    async def set_role(self, place_id: UUID, user_id: UUID, role: str) -> None:
        await self.redis.hset(f"place_roles:{place_id}", str(user_id), role)
        await self.redis.sadd(f"user_places:{user_id}", str(place_id))

    async def remove_role(self, place_id: UUID, user_id: UUID) -> None:
        await self.redis.hdel(f"place_roles:{place_id}", str(user_id))
        await self.redis.srem(f"user_places:{user_id}", str(place_id))

    async def remove_place(self, place_id: UUID) -> None:
        members = await self.redis.hkeys(f"place_roles:{place_id}")
        for user_id in members:
            uid = user_id.decode() if isinstance(user_id, bytes) else user_id
            await self.redis.srem(f"user_places:{uid}", str(place_id))
        await self.redis.delete(f"place_roles:{place_id}")

    async def get_user_places(self, user_id: UUID) -> set[str]:
        raw = await self.redis.smembers(f"user_places:{user_id}")
        return {v.decode() if isinstance(v, bytes) else v for v in raw}
