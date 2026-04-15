import json
import logging
from uuid import UUID

import aiomqtt

from src.core.authorization import check_write_permission
from src.core.exceptions import InvalidValueError, NotFoundError
from src.infra.db.models.actuator import Actuator, ActuatorValueTypeEnum
from src.infra.db.uow import UnitOfWork
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)


class CommandsService:
    def __init__(
        self, uow: UnitOfWork, role_cache: RoleCacheService, mqtt_client: aiomqtt.Client
    ) -> None:
        self.uow = uow
        self.role_cache = role_cache
        self.mqtt_client = mqtt_client

    async def send_command(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        actuator_key: str,
        value: str,
    ) -> bool:
        await check_write_permission(self.role_cache, user_id, place_id)

        device = await self.uow.device_repository.get_by_id(device_id)
        if not device or device.place_id != place_id:
            raise NotFoundError("Device not found")

        actuator = await self.uow.actuator_repository.get_one_or_none(
            device_id=device_id, key=actuator_key
        )
        if not actuator:
            raise NotFoundError(f"Actuator '{actuator_key}' not found on this device")

        self._validate_value(actuator.value_type, value, actuator)

        topic = f"placebrain/{place_id}/devices/{device_id}/command"
        payload = json.dumps({"actuator_key": actuator_key, "value": value})
        await self.mqtt_client.publish(topic, payload.encode())
        logger.info("Command sent to %s: %s=%s", topic, actuator_key, value)
        return True

    @staticmethod
    def _validate_value(value_type: ActuatorValueTypeEnum, value: str, actuator: Actuator) -> None:
        if value_type == ActuatorValueTypeEnum.BOOLEAN:
            if value.lower() not in ("true", "false"):
                raise InvalidValueError("Boolean actuator value must be 'true' or 'false'")
        elif value_type == ActuatorValueTypeEnum.NUMBER:
            try:
                num = float(value)
            except ValueError as e:
                raise InvalidValueError("Number actuator value must be numeric") from e
            if actuator.min_value is not None and num < actuator.min_value:
                raise InvalidValueError(f"Value below minimum ({actuator.min_value})")
            if actuator.max_value is not None and num > actuator.max_value:
                raise InvalidValueError(f"Value above maximum ({actuator.max_value})")
            if actuator.step is not None and actuator.step > 0:
                remainder = (num - (actuator.min_value or 0)) % actuator.step
                if abs(remainder) > 1e-9 and abs(remainder - actuator.step) > 1e-9:
                    raise InvalidValueError(f"Value must be a multiple of step ({actuator.step})")
        elif value_type == ActuatorValueTypeEnum.ENUM:
            if actuator.enum_options and value not in actuator.enum_options:
                raise InvalidValueError(f"Value must be one of: {actuator.enum_options}")
