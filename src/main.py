import asyncio
import logging

import grpc
from dishka import make_async_container
from dishka.integrations.grpcio import DishkaAioInterceptor
from faststream.kafka import KafkaBroker
from placebrain_contracts.devices_pb2_grpc import add_DevicesServiceServicer_to_server

from src.core.config import Settings
from src.dependencies.config import ConfigProvider
from src.dependencies.db import DBProvider
from src.dependencies.devices import DevicesProvider
from src.dependencies.kafka import KafkaProvider
from src.dependencies.mqtt import MqttProvider
from src.dependencies.redis import RedisProvider
from src.handlers.devices import DevicesHandler
from src.infra.kafka.consumers import on_device_status, on_places_event
from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)


async def serve() -> None:
    container = make_async_container(
        ConfigProvider(),
        DBProvider(),
        RedisProvider(),
        KafkaProvider(),
        MqttProvider(),
        DevicesProvider(),
    )
    settings = await container.get(Settings)
    logging.basicConfig(
        level=settings.logging.level_value,
        format=settings.logging.format,
        datefmt=settings.logging.date_format,
    )

    # gRPC server
    server = grpc.aio.server(interceptors=[DishkaAioInterceptor(container)])
    add_DevicesServiceServicer_to_server(DevicesHandler(), server)
    server.add_insecure_port(f"[::]:{settings.app.port}")

    logger.info("Starting devices service on port %s", settings.app.port)

    # Kafka broker (already started by KafkaProvider)
    broker = await container.get(KafkaBroker)

    # Register Kafka consumers as background tasks
    async def consume_places_events() -> None:
        async for msg in broker.subscriber("places.events", group_id="devices-service"):
            async with container() as request_container:
                role_cache = await request_container.get(RoleCacheService)
                devices_service = await request_container.get(DevicesService)
                mqtt_auth_service = await request_container.get(MqttAuthService)
                await on_places_event(msg, role_cache, devices_service, mqtt_auth_service, broker)

    async def consume_status_events() -> None:
        async for msg in broker.subscriber("telemetry.status", group_id="devices-service"):
            async with container() as request_container:
                devices_service = await request_container.get(DevicesService)
                await on_device_status(msg, devices_service)

    try:
        await server.start()
        places_task = asyncio.create_task(consume_places_events())
        status_task = asyncio.create_task(consume_status_events())
        await server.wait_for_termination()
    finally:
        places_task.cancel()
        status_task.cancel()
        await server.stop(grace=3)
        await container.close()


if __name__ == "__main__":
    asyncio.run(serve())
