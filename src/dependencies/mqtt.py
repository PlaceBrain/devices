import logging
from collections.abc import AsyncIterable
from urllib.parse import urlparse

import aiomqtt
from dishka import Provider, Scope, provide

from src.core.config import Settings

logger = logging.getLogger(__name__)


class MqttProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_mqtt_client(self, settings: Settings) -> AsyncIterable[aiomqtt.Client]:
        parsed = urlparse(settings.mqtt.url)
        hostname = parsed.hostname or "localhost"
        port = parsed.port or 1883
        client = aiomqtt.Client(hostname=hostname, port=port)
        async with client:
            logger.info("Connected to MQTT broker at %s:%d", hostname, port)
            yield client
