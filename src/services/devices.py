import asyncio
import logging
import secrets
from datetime import UTC, datetime
from uuid import UUID

import bcrypt
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.core.authorization import check_read_permission, check_write_permission
from src.core.exceptions import NotFoundError
from src.infra.db.models.device import Device, DeviceStatusEnum
from src.infra.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class DevicesService:
    def __init__(self, uow: UnitOfWork, places_stub: PlacesServiceStub) -> None:
        self.uow = uow
        self.places_stub = places_stub

    @staticmethod
    async def _generate_token() -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        loop = asyncio.get_running_loop()
        token_hash = await loop.run_in_executor(
            None, lambda: bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()
        )
        return token, token_hash

    async def create_device(self, user_id: UUID, place_id: UUID, name: str) -> tuple[str, str]:
        await check_write_permission(self.places_stub, user_id, place_id)
        token, token_hash = await self._generate_token()
        device = await self.uow.device_repository.create(
            place_id=place_id, name=name, token_hash=token_hash
        )
        return str(device.id), token

    async def get_device(self, user_id: UUID, place_id: UUID, device_id: UUID) -> Device:
        await check_read_permission(self.places_stub, user_id, place_id)
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")
        return device

    async def list_devices(
        self, user_id: UUID, place_id: UUID, page: int = 1, per_page: int = 20
    ) -> tuple[list[Device], int]:
        await check_read_permission(self.places_stub, user_id, place_id)
        filters = [Device.place_id == place_id]
        devices = await self.uow.device_repository.find(
            filters=filters,
            order_by=Device.created_at.desc(),
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        total = await self.uow.device_repository.count(filters=filters)
        return list(devices), total

    async def update_device(self, user_id: UUID, place_id: UUID, device_id: UUID, name: str) -> str:
        await check_write_permission(self.places_stub, user_id, place_id)
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")
        await self.uow.device_repository.update(device_id, name=name)
        return str(device_id)

    async def delete_device(self, user_id: UUID, place_id: UUID, device_id: UUID) -> bool:
        await check_write_permission(self.places_stub, user_id, place_id)
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")
        await self.uow.device_repository.delete(device)
        return True

    async def regenerate_token(self, user_id: UUID, place_id: UUID, device_id: UUID) -> str:
        await check_write_permission(self.places_stub, user_id, place_id)
        token, token_hash = await self._generate_token()
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")
        await self.uow.device_repository.update(device_id, token_hash=token_hash)
        return token

    async def delete_devices_by_place(self, place_id: UUID) -> tuple[int, list[str]]:
        deleted_count, device_ids = await self.uow.device_repository.delete_by_place(place_id)
        return deleted_count, device_ids

    async def update_device_status(self, device_id: UUID, status: DeviceStatusEnum) -> bool:
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device:
            raise NotFoundError("Device not found")
        update_data: dict = {"status": status}
        if status == DeviceStatusEnum.ONLINE:
            update_data["last_seen_at"] = datetime.now(UTC)
        await self.uow.device_repository.update(device_id, **update_data)
        return True

    async def get_place_id_for_device(self, device_id: UUID) -> str:
        device = await self.uow.device_repository.get_by_id(device_id)
        return str(device.place_id) if device else ""
