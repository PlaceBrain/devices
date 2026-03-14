import aiomqtt
from dishka import Provider, Scope, provide
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.infra.db.uow import UnitOfWork
from src.services.actuators import ActuatorsService
from src.services.commands import CommandsService
from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.sensors import SensorsService


class DevicesProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def provide_devices_service(
        self, uow: UnitOfWork, places_stub: PlacesServiceStub
    ) -> DevicesService:
        return DevicesService(uow, places_stub)

    @provide(scope=Scope.REQUEST)
    def provide_sensors_service(
        self, uow: UnitOfWork, places_stub: PlacesServiceStub
    ) -> SensorsService:
        return SensorsService(uow, places_stub)

    @provide(scope=Scope.REQUEST)
    def provide_actuators_service(
        self, uow: UnitOfWork, places_stub: PlacesServiceStub
    ) -> ActuatorsService:
        return ActuatorsService(uow, places_stub)

    @provide(scope=Scope.REQUEST)
    def provide_commands_service(
        self, uow: UnitOfWork, places_stub: PlacesServiceStub, mqtt_client: aiomqtt.Client
    ) -> CommandsService:
        return CommandsService(uow, places_stub, mqtt_client)

    @provide(scope=Scope.REQUEST)
    def provide_mqtt_auth_service(
        self, uow: UnitOfWork, places_stub: PlacesServiceStub
    ) -> MqttAuthService:
        return MqttAuthService(uow, places_stub)
