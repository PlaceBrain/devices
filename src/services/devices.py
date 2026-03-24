import logging
import secrets
from uuid import UUID

import bcrypt
from placebrain_contracts.places_pb2 import GetPlaceRequest
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.core.roles import WRITE_ROLES
from src.infra.db.models.device import Device, DeviceStatusEnum
from src.infra.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class DevicesService:
    def __init__(self, uow: UnitOfWork, places_stub: PlacesServiceStub) -> None:
        self.uow = uow
        self.places_stub = places_stub

    async def _check_permission(self, user_id: UUID, place_id: UUID) -> None:
        response = await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )
        if response.user_role not in WRITE_ROLES:
            raise PermissionError("Only owner or admin can manage devices")

    async def _check_read_permission(self, user_id: UUID, place_id: UUID) -> None:
        await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )

    @staticmethod
    def _generate_token() -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()
        return token, token_hash

    async def create_device(self, user_id: UUID, place_id: UUID, name: str) -> tuple[str, str]:
        await self._check_permission(user_id, place_id)
        token, token_hash = self._generate_token()
        async with self.uow:
            device = await self.uow.device_repository.create(
                place_id=place_id, name=name, token_hash=token_hash
            )
            return str(device.id), token

    async def get_device(self, user_id: UUID, place_id: UUID, device_id: UUID) -> Device:
        await self._check_read_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            return device

    async def list_devices(self, user_id: UUID, place_id: UUID) -> list[Device]:
        await self._check_read_permission(user_id, place_id)
        async with self.uow:
            devices = await self.uow.device_repository.get_all(place_id=place_id)
            return list(devices)

    async def update_device(self, user_id: UUID, place_id: UUID, device_id: UUID, name: str) -> str:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            await self.uow.device_repository.update(device_id, name=name)
            return str(device_id)

    async def delete_device(self, user_id: UUID, place_id: UUID, device_id: UUID) -> bool:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            await self.uow.device_repository.delete(device)
            return True

    async def regenerate_token(self, user_id: UUID, place_id: UUID, device_id: UUID) -> str:
        await self._check_permission(user_id, place_id)
        token, token_hash = self._generate_token()
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            await self.uow.device_repository.update(device_id, token_hash=token_hash)
            return token

    async def delete_devices_by_place(self, place_id: UUID) -> tuple[int, list[str]]:
        async with self.uow:
            deleted_count, device_ids = await self.uow.device_repository.delete_by_place(place_id)
            return deleted_count, device_ids

    async def update_device_status(self, device_id: UUID, status: DeviceStatusEnum) -> bool:
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device:
                raise ValueError("Device not found")
            from datetime import UTC, datetime

            update_data: dict = {"status": status}
            if status == DeviceStatusEnum.ONLINE:
                update_data["last_seen_at"] = datetime.now(UTC)
            await self.uow.device_repository.update(device_id, **update_data)
            return True
