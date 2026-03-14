import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
from placebrain_contracts.places_pb2 import ListPlacesRequest
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.infra.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

DEVICE_USERNAME_RE = re.compile(r"^device:(.+)$")
USER_USERNAME_RE = re.compile(r"^user:(.+)$")
COLLECTOR_USERNAME = "collector"

MQTT_CREDENTIALS_TTL = timedelta(hours=24)


class MqttAuthService:
    def __init__(self, uow: UnitOfWork, places_stub: PlacesServiceStub) -> None:
        self.uow = uow
        self.places_stub = places_stub

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

        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device:
                return False
            return bcrypt.checkpw(password.encode(), device.token_hash.encode())

    async def _authenticate_user(self, user_id_str: str, password: str) -> bool:
        async with self.uow:
            cred = await self.uow.mqtt_credential_repository.get_one_or_none(
                username=f"user:{user_id_str}"
            )
            if not cred:
                return False
            if cred.expires_at < datetime.now(UTC):
                return False
            return bcrypt.checkpw(password.encode(), cred.password_hash.encode())

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

        async with self.uow:
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

        async with self.uow:
            cred = await self.uow.mqtt_credential_repository.get_one_or_none(
                username=f"user:{user_id_str}"
            )
            if not cred:
                return False

            for place_id in cred.allowed_place_ids:
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
        places_response = await self.places_stub.ListPlaces(ListPlacesRequest(user_id=str(user_id)))
        allowed_place_ids = [p.place_id for p in places_response.places]

        password = secrets.token_urlsafe(32)
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        username = f"user:{user_id}"
        expires_at = datetime.now(UTC) + MQTT_CREDENTIALS_TTL

        async with self.uow:
            existing = await self.uow.mqtt_credential_repository.get_one_or_none(username=username)
            if existing:
                await self.uow.mqtt_credential_repository.update(
                    existing.id,
                    password_hash=password_hash,
                    allowed_place_ids=allowed_place_ids,
                    expires_at=expires_at,
                )
            else:
                await self.uow.mqtt_credential_repository.create(
                    user_id=user_id,
                    username=username,
                    password_hash=password_hash,
                    allowed_place_ids=allowed_place_ids,
                    expires_at=expires_at,
                )

        expires_at_ts = int(expires_at.timestamp())
        return username, password, expires_at_ts
