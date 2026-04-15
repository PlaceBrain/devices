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
from src.infra.kafka.routes import register_subscribers

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

    # Kafka — register subscribers, then start
    broker = await container.get(KafkaBroker)
    register_subscribers(broker, container)
    await broker.start()

    logger.info("Starting devices service on port %s", settings.app.port)

    try:
        await server.start()
        await server.wait_for_termination()
    finally:
        await broker.close()
        await server.stop(grace=3)
        await container.close()


if __name__ == "__main__":
    asyncio.run(serve())
