import asyncio
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from functools import partial
from uuid import UUID

import bcrypt
import orjson
from redis.asyncio import Redis

from src.infra.db.uow import UnitOfWork
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)

DEVICE_USERNAME_RE = re.compile(r"^device:(.+)$")
USER_USERNAME_RE = re.compile(r"^user:(.+)$")
COLLECTOR_USERNAME = "collector"

MQTT_CREDENTIALS_TTL = timedelta(hours=24)


class MqttAuthService:
    def __init__(self, uow: UnitOfWork, role_cache: RoleCacheService, redis: Redis) -> None:
        self.uow = uow
        self.role_cache = role_cache
        self.redis = redis

    async def authenticate(self, username: str, password: str) -> bool:
        if username == COLLECTOR_USERNAME:
            return True

        device_match = DEVICE_USERNAME_RE.match(username)
        if device_match:
            return await self._authenticate_device(device_match.group(1), password)

        user_match = USER_USERNAME_RE.match(username)
        if user_match:
            return await self._authenticate_user(user_match.group(1), password)

        return False

    async def _authenticate_device(self, device_id_str: str, password: str) -> bool:
        try:
            device_id = UUID(device_id_str)
        except ValueError:
            return False

        device = await self.uow.device_repository.get_by_id(device_id)
        if not device:
            return False
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(bcrypt.checkpw, password.encode(), device.token_hash.encode())
        )

    async def _authenticate_user(self, user_id_str: str, password: str) -> bool:
        redis_key = f"mqtt:cred:user:{user_id_str}"
        cached = await self.redis.hgetall(redis_key)
        if not cached:
            return False
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(bcrypt.checkpw, password.encode(), cached["password_hash"].encode())
        )

    async def check_acl(self, username: str, topic: str, action: str) -> bool:
        if username == COLLECTOR_USERNAME:
            return self._check_collector_acl(topic, action)

        device_match = DEVICE_USERNAME_RE.match(username)
        if device_match:
            return await self._check_device_acl(device_match.group(1), topic, action)

        user_match = USER_USERNAME_RE.match(username)
        if user_match:
            return await self._check_user_acl(user_match.group(1), topic, action)

        return False

    async def _check_device_acl(self, device_id_str: str, topic: str, action: str) -> bool:
        try:
            device_id = UUID(device_id_str)
        except ValueError:
            return False

        device = await self.uow.device_repository.get_by_id(device_id)
        if not device:
            return False

        place_id = str(device.place_id)
        dev_id = str(device.id)
        allowed_pub = {
            f"placebrain/{place_id}/devices/{dev_id}/telemetry",
            f"placebrain/{place_id}/devices/{dev_id}/status",
        }
        allowed_sub = {
            f"placebrain/{place_id}/devices/{dev_id}/command",
        }

        if action == "publish":
            return topic in allowed_pub
        elif action == "subscribe":
            return topic in allowed_sub
        return False

    async def _check_user_acl(self, user_id_str: str, topic: str, action: str) -> bool:
        if action == "publish":
            return False

        redis_key = f"mqtt:cred:user:{user_id_str}"
        raw = await self.redis.hget(redis_key, "allowed_place_ids")
        if not raw:
            return False

        allowed = orjson.loads(raw)
        for place_id in allowed:
            if topic.startswith(f"placebrain/{place_id}/"):
                return True
        return False

    @staticmethod
    def _check_collector_acl(topic: str, action: str) -> bool:
        if action == "subscribe":
            parts = topic.split("/")
            if len(parts) >= 5 and parts[0] == "placebrain" and parts[2] == "devices":
                return parts[4] in ("telemetry", "status")
        elif action == "publish":
            parts = topic.split("/")
            if len(parts) == 3 and parts[0] == "placebrain" and parts[2] == "alerts":
                return True
        return False

    async def generate_mqtt_credentials(self, user_id: UUID) -> tuple[str, str, int]:
        username = f"user:{user_id}"
        redis_key = f"mqtt:cred:{username}"

        cached = await self.redis.hgetall(redis_key)
        if cached:
            return cached["username"], cached["password"], int(cached["expires_at"])

        allowed_place_ids = list(await self.role_cache.get_user_places(user_id))

        password = secrets.token_urlsafe(32)
        loop = asyncio.get_running_loop()
        password_hash = await loop.run_in_executor(
            None, lambda: bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        )
        expires_at = datetime.now(UTC) + MQTT_CREDENTIALS_TTL
        expires_at_ts = int(expires_at.timestamp())
        ttl_seconds = int(MQTT_CREDENTIALS_TTL.total_seconds())

        await self.redis.hset(
            redis_key,
            mapping={
                "username": username,
                "password": password,
                "password_hash": password_hash,
                "allowed_place_ids": orjson.dumps(allowed_place_ids).decode(),
                "expires_at": str(expires_at_ts),
            },
        )
        await self.redis.expire(redis_key, ttl_seconds)

        return username, password, expires_at_ts

    async def invalidate_credentials(self, user_ids: list[str]) -> None:
        keys = [f"mqtt:cred:user:{uid}" for uid in user_ids]
        if keys:
            await self.redis.delete(*keys)
