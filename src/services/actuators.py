import logging
from uuid import UUID

from placebrain_contracts.places_pb2 import GetPlaceRequest
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.core.roles import WRITE_ROLES
from src.infra.db.models.actuator import Actuator, ActuatorValueTypeEnum
from src.infra.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


class ActuatorsService:
    def __init__(self, uow: UnitOfWork, places_stub: PlacesServiceStub) -> None:
        self.uow = uow
        self.places_stub = places_stub

    async def _check_permission(self, user_id: UUID, place_id: UUID) -> None:
        response = await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )
        if response.user_role not in WRITE_ROLES:
            raise PermissionError("Only owner or admin can manage actuators")

    async def _check_read_permission(self, user_id: UUID, place_id: UUID) -> None:
        await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )

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
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            existing = await self.uow.actuator_repository.get_one_or_none(
                device_id=device_id, key=key
            )
            if existing:
                raise ValueError("Actuator with this key already exists on this device")
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
        async with self.uow:
            actuators = await self.uow.actuator_repository.get_all(device_id=device_id)
            return list(actuators)

    async def list_actuators(
        self, user_id: UUID, place_id: UUID, device_id: UUID
    ) -> list[Actuator]:
        await self._check_read_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
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
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            actuator = await self.uow.actuator_repository.get_by_id(actuator_id)
            if not actuator or actuator.device_id != device_id:
                raise ValueError("Actuator not found")
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
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            actuator = await self.uow.actuator_repository.get_by_id(actuator_id)
            if not actuator or actuator.device_id != device_id:
                raise ValueError("Actuator not found")
            await self.uow.actuator_repository.delete(actuator)
            return True
