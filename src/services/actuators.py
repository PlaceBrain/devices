import logging
from uuid import UUID

from src.core.authorization import check_read_permission, check_write_permission
from src.core.exceptions import AlreadyExistsError, NotFoundError
from src.infra.db.models.actuator import Actuator, ActuatorValueTypeEnum
from src.infra.db.models.device import Device
from src.infra.db.uow import UnitOfWork
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)


class ActuatorsService:
    def __init__(self, uow: UnitOfWork, role_cache: RoleCacheService) -> None:
        self.uow = uow
        self.role_cache = role_cache

    async def _get_device_or_fail(self, device_id: UUID, place_id: UUID) -> Device:
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")
        return device

    async def create_actuator(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        key: str,
        name: str,
        value_type: ActuatorValueTypeEnum,
        unit_label: str,
        precision: int,
        min_value: float | None,
        max_value: float | None,
        step: float | None,
        enum_options: list[str] | None,
    ) -> str:
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        existing = await self.uow.actuator_repository.get_one_or_none(device_id=device_id, key=key)
        if existing:
            raise AlreadyExistsError("Actuator with this key already exists on this device")
        actuator = await self.uow.actuator_repository.create(
            device_id=device_id,
            key=key,
            name=name,
            value_type=value_type,
            unit_label=unit_label,
            precision=precision,
            min_value=min_value,
            max_value=max_value,
            step=step,
            enum_options=enum_options,
        )
        return str(actuator.id)

    async def list_by_device_id(self, device_id: UUID) -> list[Actuator]:
        actuators = await self.uow.actuator_repository.get_all(device_id=device_id)
        return list(actuators)

    async def list_actuators(
        self, user_id: UUID, place_id: UUID, device_id: UUID
    ) -> list[Actuator]:
        await check_read_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        actuators = await self.uow.actuator_repository.get_all(device_id=device_id)
        return list(actuators)

    async def update_actuator(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        actuator_id: UUID,
        name: str,
        unit_label: str,
        precision: int,
        min_value: float | None,
        max_value: float | None,
        step: float | None,
        enum_options: list[str] | None,
    ) -> str:
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        actuator = await self.uow.actuator_repository.get_by_id(actuator_id)
        if not actuator or actuator.device_id != device_id:
            raise NotFoundError("Actuator not found")
        await self.uow.actuator_repository.update(
            actuator_id,
            name=name,
            unit_label=unit_label,
            precision=precision,
            min_value=min_value,
            max_value=max_value,
            step=step,
            enum_options=enum_options,
        )
        return str(actuator_id)

    async def delete_actuator(
        self, user_id: UUID, place_id: UUID, device_id: UUID, actuator_id: UUID
    ) -> bool:
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        actuator = await self.uow.actuator_repository.get_by_id(actuator_id)
        if not actuator or actuator.device_id != device_id:
            raise NotFoundError("Actuator not found")
        await self.uow.actuator_repository.delete(actuator)
        return True
