import aiomqtt
from dishka import Provider, Scope, provide
from faststream.kafka import KafkaBroker
from redis.asyncio import Redis

from src.infra.db.uow import UnitOfWork
from src.services.actuators import ActuatorsService
from src.services.commands import CommandsService
from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.role_cache import RoleCacheService
from src.services.sensors import SensorsService


class DevicesProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def provide_role_cache(self, redis: Redis) -> RoleCacheService:
        return RoleCacheService(redis)

    @provide(scope=Scope.REQUEST)
    def provide_devices_service(
        self, uow: UnitOfWork, role_cache: RoleCacheService, broker: KafkaBroker
    ) -> DevicesService:
        return DevicesService(uow, role_cache, broker)

    @provide(scope=Scope.REQUEST)
    def provide_sensors_service(
        self, uow: UnitOfWork, role_cache: RoleCacheService, broker: KafkaBroker
    ) -> SensorsService:
        return SensorsService(uow, role_cache, broker)

    @provide(scope=Scope.REQUEST)
    def provide_actuators_service(
        self, uow: UnitOfWork, role_cache: RoleCacheService
    ) -> ActuatorsService:
        return ActuatorsService(uow, role_cache)

    @provide(scope=Scope.REQUEST)
    def provide_commands_service(
        self, uow: UnitOfWork, role_cache: RoleCacheService, mqtt_client: aiomqtt.Client
    ) -> CommandsService:
        return CommandsService(uow, role_cache, mqtt_client)

    @provide(scope=Scope.REQUEST)
    def provide_mqtt_auth_service(
        self, uow: UnitOfWork, role_cache: RoleCacheService, redis: Redis
    ) -> MqttAuthService:
        return MqttAuthService(uow, role_cache, redis)
