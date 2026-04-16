import logging
from uuid import UUID

from faststream.kafka import KafkaBroker
from placebrain_contracts.events import (
    TOPIC_THRESHOLD_CREATED,
    TOPIC_THRESHOLD_DELETED,
    ThresholdCreated,
    ThresholdDeleted,
)

from src.core.authorization import check_read_permission, check_write_permission
from src.core.exceptions import AlreadyExistsError, NotFoundError
from src.infra.db.models.sensor import Sensor, ValueTypeEnum
from src.infra.db.models.sensor_threshold import (
    SensorThreshold,
    ThresholdSeverityEnum,
    ThresholdTypeEnum,
)
from src.infra.db.uow import UnitOfWork
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)


class SensorsService:
    def __init__(self, uow: UnitOfWork, role_cache: RoleCacheService, broker: KafkaBroker) -> None:
        self.uow = uow
        self.role_cache = role_cache
        self.broker = broker

    async def _get_device_or_fail(self, device_id: UUID, place_id: UUID) -> None:
        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")

    async def _get_sensor_or_fail(self, sensor_id: UUID, device_id: UUID) -> Sensor:
        sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
        if not sensor or sensor.device_id != device_id:
            raise NotFoundError("Sensor not found")
        return sensor

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
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        existing = await self.uow.sensor_repository.get_one_or_none(device_id=device_id, key=key)
        if existing:
            raise AlreadyExistsError("Sensor with this key already exists on this device")
        sensor = await self.uow.sensor_repository.create(
            device_id=device_id,
            key=key,
            name=name,
            value_type=value_type,
            unit_label=unit_label,
            precision=precision,
        )
        return str(sensor.id)

    async def list_by_device_id(self, device_id: UUID) -> list[Sensor]:
        sensors = await self.uow.sensor_repository.get_all(device_id=device_id)
        return list(sensors)

    async def list_sensors(self, user_id: UUID, place_id: UUID, device_id: UUID) -> list[Sensor]:
        await check_read_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
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
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        await self._get_sensor_or_fail(sensor_id, device_id)
        await self.uow.sensor_repository.update(
            sensor_id, name=name, unit_label=unit_label, precision=precision
        )
        return str(sensor_id)

    async def delete_sensor(
        self, user_id: UUID, place_id: UUID, device_id: UUID, sensor_id: UUID
    ) -> bool:
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        sensor = await self.uow.sensor_repository.get_by_id(sensor_id)
        if not sensor or sensor.device_id != device_id:
            raise NotFoundError("Sensor not found")
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
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        sensor = await self._get_sensor_or_fail(sensor_id, device_id)
        threshold = await self.uow.sensor_threshold_repository.create(
            sensor_id=sensor_id, type=type, value=value, severity=severity
        )
        await self.broker.publish(
            ThresholdCreated(
                sensor_id=sensor_id,
                device_id=device_id,
                key=sensor.key,
                threshold_id=threshold.id,
                threshold_type=type.value,
                value=value,
                severity=severity.value,
            ),
            topic=TOPIC_THRESHOLD_CREATED,
            key=str(sensor_id).encode(),
        )
        return str(threshold.id)

    async def list_thresholds(
        self, user_id: UUID, place_id: UUID, device_id: UUID, sensor_id: UUID
    ) -> list[SensorThreshold]:
        await check_read_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        await self._get_sensor_or_fail(sensor_id, device_id)
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
        await check_write_permission(self.role_cache, user_id, place_id)
        await self._get_device_or_fail(device_id, place_id)
        sensor = await self._get_sensor_or_fail(sensor_id, device_id)
        threshold = await self.uow.sensor_threshold_repository.get_by_id(threshold_id)
        if not threshold or threshold.sensor_id != sensor_id:
            raise NotFoundError("Threshold not found")
        await self.uow.sensor_threshold_repository.delete(threshold)
        await self.broker.publish(
            ThresholdDeleted(
                sensor_id=sensor_id,
                device_id=device_id,
                key=sensor.key,
                threshold_id=threshold_id,
            ),
            topic=TOPIC_THRESHOLD_DELETED,
            key=str(sensor_id).encode(),
        )
        return True

    async def get_sensor_thresholds(self, sensor_id: UUID) -> list[SensorThreshold]:
        thresholds = await self.uow.sensor_threshold_repository.get_all(sensor_id=sensor_id)
        return list(thresholds)

    async def get_all_thresholds(self) -> list[tuple[Sensor, list[SensorThreshold]]]:
        sensors = await self.uow.sensor_repository.get_all()
        result: list[tuple[Sensor, list[SensorThreshold]]] = []
        for sensor in sensors:
            thresholds = await self.uow.sensor_threshold_repository.get_all(sensor_id=sensor.id)
            if thresholds:
                result.append((sensor, list(thresholds)))
        return result
