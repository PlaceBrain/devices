import logging
from typing import Any

from dishka import AsyncContainer
from faststream.kafka import KafkaBroker

from src.infra.kafka.consumers import handle_device_status, handle_places_event
from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)


def register_subscribers(broker: KafkaBroker, container: AsyncContainer) -> None:
    @broker.subscriber("places.events", group_id="devices-service", no_ack=True)
    async def on_places_event(msg: dict[str, Any]) -> None:
        async with container() as request_container:
            role_cache = await request_container.get(RoleCacheService)
            devices_service = await request_container.get(DevicesService)
            mqtt_auth_service = await request_container.get(MqttAuthService)
            await handle_places_event(msg, role_cache, devices_service, mqtt_auth_service, broker)

    @broker.subscriber("telemetry.status", group_id="devices-service", no_ack=True)
    async def on_device_status(msg: dict[str, Any]) -> None:
        async with container() as request_container:
            devices_service = await request_container.get(DevicesService)
            await handle_device_status(msg, devices_service)
