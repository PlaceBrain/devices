import json
import logging
from uuid import UUID

import aiomqtt
from placebrain_contracts.places_pb2 import GetPlaceRequest
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.infra.db.models.actuator import ActuatorValueTypeEnum
from src.infra.db.uow import UnitOfWork

logger = logging.getLogger(__name__)

_WRITE_ROLES = {1, 2}  # ROLE_OWNER, ROLE_ADMIN


class CommandsService:
    def __init__(
        self, uow: UnitOfWork, places_stub: PlacesServiceStub, mqtt_client: aiomqtt.Client
    ) -> None:
        self.uow = uow
        self.places_stub = places_stub
        self.mqtt_client = mqtt_client

    async def send_command(
        self,
        user_id: UUID,
        place_id: UUID,
        device_id: UUID,
        actuator_key: str,
        value: str,
    ) -> bool:
        response = await self.places_stub.GetPlace(
            GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
        )
        if response.user_role not in _WRITE_ROLES:
            raise PermissionError("Only owner or admin can send commands")

        async with self.uow:
            device = await self.uow.device_repository.get_by_id(device_id)
            if not device or device.place_id != place_id:
                raise ValueError("Device not found")

            actuator = await self.uow.actuator_repository.get_one_or_none(
                device_id=device_id, key=actuator_key
            )
            if not actuator:
                raise ValueError(f"Actuator '{actuator_key}' not found on this device")

            self._validate_value(actuator.value_type, value, actuator)

        topic = f"placebrain/{place_id}/devices/{device_id}/command"
        payload = json.dumps({"actuator_key": actuator_key, "value": value})
        await self.mqtt_client.publish(topic, payload.encode())
        logger.info("Command sent to %s: %s=%s", topic, actuator_key, value)
        return True

    @staticmethod
    def _validate_value(value_type: ActuatorValueTypeEnum, value: str, actuator: object) -> None:
        if value_type == ActuatorValueTypeEnum.BOOLEAN:
            if value.lower() not in ("true", "false"):
                raise ValueError("Boolean actuator value must be 'true' or 'false'")
        elif value_type == ActuatorValueTypeEnum.NUMBER:
            try:
                num = float(value)
            except ValueError:
                raise ValueError("Number actuator value must be numeric") from None
            if actuator.min_value is not None and num < actuator.min_value:  # type: ignore[union-attr]
                raise ValueError(f"Value below minimum ({actuator.min_value})")  # type: ignore[union-attr]
            if actuator.max_value is not None and num > actuator.max_value:  # type: ignore[union-attr]
                raise ValueError(f"Value above maximum ({actuator.max_value})")  # type: ignore[union-attr]
            if actuator.step is not None and actuator.step > 0:  # type: ignore[union-attr]
                remainder = (num - (actuator.min_value or 0)) % actuator.step  # type: ignore[union-attr]
                if abs(remainder) > 1e-9 and abs(remainder - actuator.step) > 1e-9:  # type: ignore[union-attr]
                    raise ValueError(f"Value must be a multiple of step ({actuator.step})")  # type: ignore[union-attr]
        elif value_type == ActuatorValueTypeEnum.ENUM:
            if actuator.enum_options and value not in actuator.enum_options:  # type: ignore[union-attr]
                raise ValueError(f"Value must be one of: {actuator.enum_options}")  # type: ignore[union-attr]
