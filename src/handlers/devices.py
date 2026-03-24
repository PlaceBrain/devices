import logging
from uuid import UUID

import grpc
from dishka import FromDishka
from dishka.integrations.grpcio import inject
from placebrain_contracts.devices_pb2 import (
    ActuatorInfo,
    AuthenticateDeviceRequest,
    AuthenticateDeviceResponse,
    CheckDeviceAclRequest,
    CheckDeviceAclResponse,
    CreateActuatorRequest,
    CreateActuatorResponse,
    CreateDeviceRequest,
    CreateDeviceResponse,
    CreateSensorRequest,
    CreateSensorResponse,
    DeleteActuatorRequest,
    DeleteActuatorResponse,
    DeleteDeviceRequest,
    DeleteDeviceResponse,
    DeleteDevicesByPlaceRequest,
    DeleteDevicesByPlaceResponse,
    DeleteSensorRequest,
    DeleteSensorResponse,
    DeleteThresholdRequest,
    DeleteThresholdResponse,
    DeviceInfo,
    DeviceSummary,
    GenerateMqttCredentialsRequest,
    GenerateMqttCredentialsResponse,
    GetAllThresholdsRequest,
    GetAllThresholdsResponse,
    GetDeviceRequest,
    GetDeviceResponse,
    GetSensorThresholdsRequest,
    GetSensorThresholdsResponse,
    ListActuatorsRequest,
    ListActuatorsResponse,
    ListDevicesRequest,
    ListDevicesResponse,
    ListSensorsRequest,
    ListSensorsResponse,
    ListThresholdsRequest,
    ListThresholdsResponse,
    RegenerateDeviceTokenRequest,
    RegenerateDeviceTokenResponse,
    SendCommandRequest,
    SendCommandResponse,
    SensorInfo,
    SensorWithThresholds,
    SetThresholdRequest,
    SetThresholdResponse,
    ThresholdInfo,
    UpdateActuatorRequest,
    UpdateActuatorResponse,
    UpdateDeviceRequest,
    UpdateDeviceResponse,
    UpdateDeviceStatusRequest,
    UpdateDeviceStatusResponse,
    UpdateSensorRequest,
    UpdateSensorResponse,
)
from placebrain_contracts.devices_pb2_grpc import DevicesServiceServicer

from src.infra.db.models.actuator import ActuatorValueTypeEnum
from src.infra.db.models.device import DeviceStatusEnum
from src.infra.db.models.sensor import ValueTypeEnum
from src.infra.db.models.sensor_threshold import ThresholdSeverityEnum, ThresholdTypeEnum
from src.services.actuators import ActuatorsService
from src.services.commands import CommandsService
from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.sensors import SensorsService

logger = logging.getLogger(__name__)

_STATUS_TO_PROTO = {
    DeviceStatusEnum.ONLINE: 1,
    DeviceStatusEnum.OFFLINE: 2,
}

_PROTO_TO_STATUS = {
    1: DeviceStatusEnum.ONLINE,
    2: DeviceStatusEnum.OFFLINE,
}

_VALUE_TYPE_TO_PROTO = {
    ValueTypeEnum.NUMBER: 1,
    ValueTypeEnum.BOOLEAN: 2,
}

_PROTO_TO_VALUE_TYPE = {
    1: ValueTypeEnum.NUMBER,
    2: ValueTypeEnum.BOOLEAN,
}

_ACTUATOR_VALUE_TYPE_TO_PROTO = {
    ActuatorValueTypeEnum.NUMBER: 1,
    ActuatorValueTypeEnum.BOOLEAN: 2,
    ActuatorValueTypeEnum.ENUM: 3,
}

_PROTO_TO_ACTUATOR_VALUE_TYPE = {
    1: ActuatorValueTypeEnum.NUMBER,
    2: ActuatorValueTypeEnum.BOOLEAN,
    3: ActuatorValueTypeEnum.ENUM,
}

_THRESHOLD_TYPE_TO_PROTO = {
    ThresholdTypeEnum.MIN: 1,
    ThresholdTypeEnum.MAX: 2,
}

_PROTO_TO_THRESHOLD_TYPE = {
    1: ThresholdTypeEnum.MIN,
    2: ThresholdTypeEnum.MAX,
}

_SEVERITY_TO_PROTO = {
    ThresholdSeverityEnum.WARNING: 1,
    ThresholdSeverityEnum.CRITICAL: 2,
}

_PROTO_TO_SEVERITY = {
    1: ThresholdSeverityEnum.WARNING,
    2: ThresholdSeverityEnum.CRITICAL,
}


class DevicesHandler(DevicesServiceServicer):
    # --- Devices ---

    @inject
    async def CreateDevice(  # type: ignore[override]
        self,
        request: CreateDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> CreateDeviceResponse:
        logger.info("CreateDevice called by user: %s", request.user_id)
        try:
            device_id, token = await devices_service.create_device(
                UUID(request.user_id), UUID(request.place_id), request.name
            )
            return CreateDeviceResponse(device_id=device_id, token=token)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def GetDevice(  # type: ignore[override]
        self,
        request: GetDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
        sensors_service: FromDishka[SensorsService],
        actuators_service: FromDishka[ActuatorsService],
    ) -> GetDeviceResponse:
        logger.info("GetDevice called for device: %s", request.device_id)
        try:
            device = await devices_service.get_device(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            sensors = await sensors_service.list_sensors(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            actuators = await actuators_service.list_actuators(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return GetDeviceResponse(
                device=DeviceInfo(
                    device_id=str(device.id),
                    place_id=str(device.place_id),
                    name=device.name,
                    status=_STATUS_TO_PROTO.get(device.status, 0),
                    last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else "",
                    created_at=device.created_at.isoformat(),
                    updated_at=device.updated_at.isoformat(),
                    sensors=[
                        SensorInfo(
                            sensor_id=str(s.id),
                            device_id=str(s.device_id),
                            key=s.key,
                            name=s.name,
                            value_type=_VALUE_TYPE_TO_PROTO.get(s.value_type, 0),
                            unit_label=s.unit_label,
                            precision=s.precision,
                        )
                        for s in sensors
                    ],
                    actuators=[
                        ActuatorInfo(
                            actuator_id=str(a.id),
                            device_id=str(a.device_id),
                            key=a.key,
                            name=a.name,
                            value_type=_ACTUATOR_VALUE_TYPE_TO_PROTO.get(a.value_type, 0),
                            unit_label=a.unit_label,
                            precision=a.precision,
                            min_value=a.min_value or 0,
                            max_value=a.max_value or 0,
                            step=a.step or 0,
                            enum_options=a.enum_options or [],
                        )
                        for a in actuators
                    ],
                )
            )
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def ListDevices(  # type: ignore[override]
        self,
        request: ListDevicesRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> ListDevicesResponse:
        logger.info("ListDevices called for place: %s", request.place_id)
        try:
            devices = await devices_service.list_devices(
                UUID(request.user_id), UUID(request.place_id)
            )
            return ListDevicesResponse(
                devices=[
                    DeviceSummary(
                        device_id=str(d.id),
                        place_id=str(d.place_id),
                        name=d.name,
                        status=_STATUS_TO_PROTO.get(d.status, 0),
                        last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else "",
                    )
                    for d in devices
                ]
            )
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def UpdateDevice(  # type: ignore[override]
        self,
        request: UpdateDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> UpdateDeviceResponse:
        logger.info("UpdateDevice called for device: %s", request.device_id)
        try:
            device_id = await devices_service.update_device(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                request.name,
            )
            return UpdateDeviceResponse(device_id=device_id)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteDevice(  # type: ignore[override]
        self,
        request: DeleteDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> DeleteDeviceResponse:
        logger.info("DeleteDevice called for device: %s", request.device_id)
        try:
            success = await devices_service.delete_device(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return DeleteDeviceResponse(success=success)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteDevicesByPlace(  # type: ignore[override]
        self,
        request: DeleteDevicesByPlaceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> DeleteDevicesByPlaceResponse:
        logger.info("DeleteDevicesByPlace called for place: %s", request.place_id)
        try:
            deleted_count, device_ids = await devices_service.delete_devices_by_place(
                UUID(request.place_id)
            )
            return DeleteDevicesByPlaceResponse(
                success=True, deleted_count=deleted_count, device_ids=device_ids
            )
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            raise

    @inject
    async def RegenerateDeviceToken(  # type: ignore[override]
        self,
        request: RegenerateDeviceTokenRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> RegenerateDeviceTokenResponse:
        logger.info("RegenerateDeviceToken called for device: %s", request.device_id)
        try:
            token = await devices_service.regenerate_token(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return RegenerateDeviceTokenResponse(token=token)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- Sensors ---

    @inject
    async def CreateSensor(  # type: ignore[override]
        self,
        request: CreateSensorRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> CreateSensorResponse:
        logger.info("CreateSensor called for device: %s", request.device_id)
        try:
            value_type = _PROTO_TO_VALUE_TYPE.get(request.value_type, ValueTypeEnum.NUMBER)
            sensor_id = await sensors_service.create_sensor(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                request.key,
                request.name,
                value_type,
                request.unit_label,
                request.precision,
            )
            return CreateSensorResponse(sensor_id=sensor_id)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
            raise

    @inject
    async def ListSensors(  # type: ignore[override]
        self,
        request: ListSensorsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> ListSensorsResponse:
        logger.info("ListSensors called for device: %s", request.device_id)
        try:
            sensors = await sensors_service.list_sensors(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return ListSensorsResponse(
                sensors=[
                    SensorInfo(
                        sensor_id=str(s.id),
                        device_id=str(s.device_id),
                        key=s.key,
                        name=s.name,
                        value_type=_VALUE_TYPE_TO_PROTO.get(s.value_type, 0),
                        unit_label=s.unit_label,
                        precision=s.precision,
                    )
                    for s in sensors
                ]
            )
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def UpdateSensor(  # type: ignore[override]
        self,
        request: UpdateSensorRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> UpdateSensorResponse:
        logger.info("UpdateSensor called for sensor: %s", request.sensor_id)
        try:
            sensor_id = await sensors_service.update_sensor(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
                request.name,
                request.unit_label,
                request.precision,
            )
            return UpdateSensorResponse(sensor_id=sensor_id)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteSensor(  # type: ignore[override]
        self,
        request: DeleteSensorRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> DeleteSensorResponse:
        logger.info("DeleteSensor called for sensor: %s", request.sensor_id)
        try:
            success = await sensors_service.delete_sensor(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
            )
            return DeleteSensorResponse(success=success)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- Thresholds ---

    @inject
    async def SetThreshold(  # type: ignore[override]
        self,
        request: SetThresholdRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> SetThresholdResponse:
        logger.info("SetThreshold called for sensor: %s", request.sensor_id)
        try:
            threshold_type = _PROTO_TO_THRESHOLD_TYPE.get(request.type, ThresholdTypeEnum.MIN)
            severity = _PROTO_TO_SEVERITY.get(request.severity, ThresholdSeverityEnum.WARNING)
            threshold_id = await sensors_service.set_threshold(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
                threshold_type,
                request.value,
                severity,
            )
            return SetThresholdResponse(threshold_id=threshold_id)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def ListThresholds(  # type: ignore[override]
        self,
        request: ListThresholdsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> ListThresholdsResponse:
        logger.info("ListThresholds called for sensor: %s", request.sensor_id)
        try:
            thresholds = await sensors_service.list_thresholds(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
            )
            return ListThresholdsResponse(
                thresholds=[
                    ThresholdInfo(
                        threshold_id=str(t.id),
                        sensor_id=str(t.sensor_id),
                        type=_THRESHOLD_TYPE_TO_PROTO.get(t.type, 0),
                        value=t.value,
                        severity=_SEVERITY_TO_PROTO.get(t.severity, 0),
                    )
                    for t in thresholds
                ]
            )
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteThreshold(  # type: ignore[override]
        self,
        request: DeleteThresholdRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> DeleteThresholdResponse:
        logger.info("DeleteThreshold called for threshold: %s", request.threshold_id)
        try:
            success = await sensors_service.delete_threshold(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
                UUID(request.threshold_id),
            )
            return DeleteThresholdResponse(success=success)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def GetSensorThresholds(  # type: ignore[override]
        self,
        request: GetSensorThresholdsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> GetSensorThresholdsResponse:
        logger.info("GetSensorThresholds called for sensor: %s", request.sensor_id)
        thresholds = await sensors_service.get_sensor_thresholds(UUID(request.sensor_id))
        return GetSensorThresholdsResponse(
            thresholds=[
                ThresholdInfo(
                    threshold_id=str(t.id),
                    sensor_id=str(t.sensor_id),
                    type=_THRESHOLD_TYPE_TO_PROTO.get(t.type, 0),
                    value=t.value,
                    severity=_SEVERITY_TO_PROTO.get(t.severity, 0),
                )
                for t in thresholds
            ]
        )

    # --- Actuators ---

    @inject
    async def CreateActuator(  # type: ignore[override]
        self,
        request: CreateActuatorRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> CreateActuatorResponse:
        logger.info("CreateActuator called for device: %s", request.device_id)
        try:
            value_type = _PROTO_TO_ACTUATOR_VALUE_TYPE.get(
                request.value_type, ActuatorValueTypeEnum.NUMBER
            )
            actuator_id = await actuators_service.create_actuator(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                request.key,
                request.name,
                value_type,
                request.unit_label,
                request.precision,
                request.min_value or None,
                request.max_value or None,
                request.step or None,
                list(request.enum_options) or None,
            )
            return CreateActuatorResponse(actuator_id=actuator_id)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
            raise

    @inject
    async def ListActuators(  # type: ignore[override]
        self,
        request: ListActuatorsRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> ListActuatorsResponse:
        logger.info("ListActuators called for device: %s", request.device_id)
        try:
            actuators = await actuators_service.list_actuators(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return ListActuatorsResponse(
                actuators=[
                    ActuatorInfo(
                        actuator_id=str(a.id),
                        device_id=str(a.device_id),
                        key=a.key,
                        name=a.name,
                        value_type=_ACTUATOR_VALUE_TYPE_TO_PROTO.get(a.value_type, 0),
                        unit_label=a.unit_label,
                        precision=a.precision,
                        min_value=a.min_value or 0,
                        max_value=a.max_value or 0,
                        step=a.step or 0,
                        enum_options=a.enum_options or [],
                    )
                    for a in actuators
                ]
            )
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def UpdateActuator(  # type: ignore[override]
        self,
        request: UpdateActuatorRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> UpdateActuatorResponse:
        logger.info("UpdateActuator called for actuator: %s", request.actuator_id)
        try:
            actuator_id = await actuators_service.update_actuator(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.actuator_id),
                request.name,
                request.unit_label,
                request.precision,
                request.min_value or None,
                request.max_value or None,
                request.step or None,
                list(request.enum_options) or None,
            )
            return UpdateActuatorResponse(actuator_id=actuator_id)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteActuator(  # type: ignore[override]
        self,
        request: DeleteActuatorRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> DeleteActuatorResponse:
        logger.info("DeleteActuator called for actuator: %s", request.actuator_id)
        try:
            success = await actuators_service.delete_actuator(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.actuator_id),
            )
            return DeleteActuatorResponse(success=success)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- Commands ---

    @inject
    async def SendCommand(  # type: ignore[override]
        self,
        request: SendCommandRequest,
        context: grpc.aio.ServicerContext,
        commands_service: FromDishka[CommandsService],
    ) -> SendCommandResponse:
        logger.info("SendCommand called for device: %s", request.device_id)
        try:
            success = await commands_service.send_command(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                request.actuator_key,
                request.value,
            )
            return SendCommandResponse(success=success)
        except PermissionError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            raise

    # --- MQTT auth ---

    @inject
    async def AuthenticateDevice(  # type: ignore[override]
        self,
        request: AuthenticateDeviceRequest,
        context: grpc.aio.ServicerContext,
        mqtt_auth_service: FromDishka[MqttAuthService],
    ) -> AuthenticateDeviceResponse:
        logger.info("AuthenticateDevice called for: %s", request.username)
        allow = await mqtt_auth_service.authenticate(request.username, request.password)
        return AuthenticateDeviceResponse(allow=allow)

    @inject
    async def CheckDeviceAcl(  # type: ignore[override]
        self,
        request: CheckDeviceAclRequest,
        context: grpc.aio.ServicerContext,
        mqtt_auth_service: FromDishka[MqttAuthService],
    ) -> CheckDeviceAclResponse:
        logger.info("CheckDeviceAcl called for: %s topic=%s", request.username, request.topic)
        allow = await mqtt_auth_service.check_acl(request.username, request.topic, request.action)
        return CheckDeviceAclResponse(allow=allow)

    # --- MQTT credentials ---

    @inject
    async def GenerateMqttCredentials(  # type: ignore[override]
        self,
        request: GenerateMqttCredentialsRequest,
        context: grpc.aio.ServicerContext,
        mqtt_auth_service: FromDishka[MqttAuthService],
    ) -> GenerateMqttCredentialsResponse:
        logger.info("GenerateMqttCredentials called for user: %s", request.user_id)
        username, password, expires_at = await mqtt_auth_service.generate_mqtt_credentials(
            UUID(request.user_id)
        )
        return GenerateMqttCredentialsResponse(
            username=username, password=password, expires_at=expires_at
        )

    # --- Device status ---

    @inject
    async def UpdateDeviceStatus(  # type: ignore[override]
        self,
        request: UpdateDeviceStatusRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> UpdateDeviceStatusResponse:
        logger.info("UpdateDeviceStatus called for device: %s", request.device_id)
        try:
            status = _PROTO_TO_STATUS.get(request.status, DeviceStatusEnum.OFFLINE)
            success = await devices_service.update_device_status(UUID(request.device_id), status)
            return UpdateDeviceStatusResponse(success=success)
        except ValueError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- GetAllThresholds (for collector) ---

    @inject
    async def GetAllThresholds(  # type: ignore[override]
        self,
        request: GetAllThresholdsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
        devices_service: FromDishka[DevicesService],
    ) -> GetAllThresholdsResponse:
        logger.info("GetAllThresholds called")
        sensor_threshold_pairs = await sensors_service.get_all_thresholds()
        device_cache: dict[UUID, str] = {}
        result = []
        for sensor, thresholds in sensor_threshold_pairs:
            if sensor.device_id not in device_cache:
                async with devices_service.uow:
                    device = await devices_service.uow.device_repository.get_by_id(sensor.device_id)
                    device_cache[sensor.device_id] = str(device.place_id) if device else ""
            place_id = device_cache[sensor.device_id]
            result.append(
                SensorWithThresholds(
                    sensor_id=str(sensor.id),
                    device_id=str(sensor.device_id),
                    place_id=place_id,
                    key=sensor.key,
                    thresholds=[
                        ThresholdInfo(
                            threshold_id=str(t.id),
                            sensor_id=str(t.sensor_id),
                            type=_THRESHOLD_TYPE_TO_PROTO.get(t.type, 0),
                            value=t.value,
                            severity=_SEVERITY_TO_PROTO.get(t.severity, 0),
                        )
                        for t in thresholds
                    ],
                )
            )
        return GetAllThresholdsResponse(sensors=result)
