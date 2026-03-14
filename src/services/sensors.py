import logging
from uuid import UUID

from placebrain_contracts.places_pb2 import GetPlaceRequest
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.infra.db.models.sensor import Sensor, ValueTypeEnum
from src.infra.db.models.sensor_threshold import (
    SensorThreshold,
    ThresholdSeverityEnum,
    ThresholdTypeEnum,
)
from src.infra.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

_WRITE_ROLES = {1, 2}  # ROLE_OWNER, ROLE_ADMIN


class SensorsService:
    def __init__(self, uow: UnitOfWork, places_stub: PlacesServiceStub) -> None:
        self.uow = uow
        self.places_stub = places_stub

    async def _check_permission(self, user_id: UUID, place_id: UUID) -> None:
        response = await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )
        if response.user_role not in _WRITE_ROLES:
            raise PermissionError("Only owner or admin can manage sensors")

    async def _check_read_permission(self, user_id: UUID, place_id: UUID) -> None:
        await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )

    async def _get_device_or_fail(self, device_id: UUID, place_id: UUID) -> None:
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")

    async def create_sensor(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        key: str,
        name: str,
        value_type: ValueTypeEnum,
        unit_label: str,
        precision: int,
    ) -> str:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            existing = await self.uow.sensor_repository.get_one_or_none(
                device_id=device_id, key=key
            )
            if existing:
                raise ValueError("Sensor with this key already exists on this device")
            sensor = await self.uow.sensor_repository.create(
                device_id=device_id,
                key=key,
                name=name,
                value_type=value_type,
                unit_label=unit_label,
                precision=precision,
            )
            return str(sensor.id)

    async def list_sensors(self, user_id: UUID, place_id: UUID, device_id: UUID) -> list[Sensor]:
        await self._check_read_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            sensors = await self.uow.sensor_repository.get_all(device_id=device_id)
            return list(sensors)

    async def update_sensor(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        sensor_id: UUID,
        name: str,
        unit_label: str,
        precision: int,
    ) -> str:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
            if not sensor or sensor.device_id != device_id:
                raise ValueError("Sensor not found")
            await self.uow.sensor_repository.update(
                sensor_id, name=name, unit_label=unit_label, precision=precision
            )
            return str(sensor_id)

    async def delete_sensor(
        self, user_id: UUID, place_id: UUID, device_id: UUID, sensor_id: UUID
    ) -> bool:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
            if not sensor or sensor.device_id != device_id:
                raise ValueError("Sensor not found")
            await self.uow.sensor_repository.delete(sensor)
            return True

    async def set_threshold(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        sensor_id: UUID,
        type: ThresholdTypeEnum,
        value: float,
        severity: ThresholdSeverityEnum,
    ) -> str:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
            if not sensor or sensor.device_id != device_id:
                raise ValueError("Sensor not found")
            threshold = await self.uow.sensor_threshold_repository.create(
                sensor_id=sensor_id, type=type, value=value, severity=severity
            )
            return str(threshold.id)

    async def list_thresholds(
        self, user_id: UUID, place_id: UUID, device_id: UUID, sensor_id: UUID
    ) -> list[SensorThreshold]:
        await self._check_read_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
            if not sensor or sensor.device_id != device_id:
                raise ValueError("Sensor not found")
            thresholds = await self.uow.sensor_threshold_repository.get_all(sensor_id=sensor_id)
            return list(thresholds)

    async def delete_threshold(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        sensor_id: UUID,
        threshold_id: UUID,
    ) -> bool:
        await self._check_permission(user_id, place_id)
        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")
            sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
            if not sensor or sensor.device_id != device_id:
                raise ValueError("Sensor not found")
            threshold = await self.uow.sensor_threshold_repository.get_by_id(threshold_id)
            if not threshold or threshold.sensor_id != sensor_id:
                raise ValueError("Threshold not found")
            await self.uow.sensor_threshold_repository.delete(threshold)
            return True

    async def get_sensor_thresholds(self, sensor_id: UUID) -> list[SensorThreshold]:
        async with self.uow:
            thresholds = await self.uow.sensor_threshold_repository.get_all(sensor_id=sensor_id)
            return list(thresholds)
