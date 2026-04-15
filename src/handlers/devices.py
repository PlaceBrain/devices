import logging
from uuid import UUID

import grpc
from dishka import FromDishka
from dishka.integrations.grpcio import inject
from placebrain_contracts import devices_pb2 as devices_pb
from placebrain_contracts.devices_pb2 import (
    DEVICE_STATUS_OFFLINE,
    DEVICE_STATUS_ONLINE,
    THRESHOLD_SEVERITY_CRITICAL,
    THRESHOLD_SEVERITY_WARNING,
    THRESHOLD_TYPE_MAX,
    THRESHOLD_TYPE_MIN,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_ENUM,
    VALUE_TYPE_NUMBER,
)
from placebrain_contracts.devices_pb2_grpc import DevicesServiceServicer

from src.core.exceptions import (
    AlreadyExistsError,
    InvalidValueError,
    NotFoundError,
    PermissionDeniedError,
)
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
    DeviceStatusEnum.ONLINE: DEVICE_STATUS_ONLINE,
    DeviceStatusEnum.OFFLINE: DEVICE_STATUS_OFFLINE,
}

_PROTO_TO_STATUS = {
    DEVICE_STATUS_ONLINE: DeviceStatusEnum.ONLINE,
    DEVICE_STATUS_OFFLINE: DeviceStatusEnum.OFFLINE,
}

_VALUE_TYPE_TO_PROTO = {
    ValueTypeEnum.NUMBER: VALUE_TYPE_NUMBER,
    ValueTypeEnum.BOOLEAN: VALUE_TYPE_BOOLEAN,
}

_PROTO_TO_VALUE_TYPE = {
    VALUE_TYPE_NUMBER: ValueTypeEnum.NUMBER,
    VALUE_TYPE_BOOLEAN: ValueTypeEnum.BOOLEAN,
}

_ACTUATOR_VALUE_TYPE_TO_PROTO = {
    ActuatorValueTypeEnum.NUMBER: VALUE_TYPE_NUMBER,
    ActuatorValueTypeEnum.BOOLEAN: VALUE_TYPE_BOOLEAN,
    ActuatorValueTypeEnum.ENUM: VALUE_TYPE_ENUM,
}

_PROTO_TO_ACTUATOR_VALUE_TYPE = {
    VALUE_TYPE_NUMBER: ActuatorValueTypeEnum.NUMBER,
    VALUE_TYPE_BOOLEAN: ActuatorValueTypeEnum.BOOLEAN,
    VALUE_TYPE_ENUM: ActuatorValueTypeEnum.ENUM,
}

_THRESHOLD_TYPE_TO_PROTO = {
    ThresholdTypeEnum.MIN: THRESHOLD_TYPE_MIN,
    ThresholdTypeEnum.MAX: THRESHOLD_TYPE_MAX,
}

_PROTO_TO_THRESHOLD_TYPE = {
    THRESHOLD_TYPE_MIN: ThresholdTypeEnum.MIN,
    THRESHOLD_TYPE_MAX: ThresholdTypeEnum.MAX,
}

_SEVERITY_TO_PROTO = {
    ThresholdSeverityEnum.WARNING: THRESHOLD_SEVERITY_WARNING,
    ThresholdSeverityEnum.CRITICAL: THRESHOLD_SEVERITY_CRITICAL,
}

_PROTO_TO_SEVERITY = {
    THRESHOLD_SEVERITY_WARNING: ThresholdSeverityEnum.WARNING,
    THRESHOLD_SEVERITY_CRITICAL: ThresholdSeverityEnum.CRITICAL,
}


class DevicesHandler(DevicesServiceServicer):
    # --- Devices ---

    @inject
    async def CreateDevice(  # type: ignore[override]
        self,
        request: devices_pb.CreateDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> devices_pb.CreateDeviceResponse:
        logger.info("CreateDevice called by user: %s", request.user_id)
        try:
            device_id, token = await devices_service.create_device(
                UUID(request.user_id), UUID(request.place_id), request.name
            )
            return devices_pb.CreateDeviceResponse(device_id=device_id, token=token)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def GetDevice(  # type: ignore[override]
        self,
        request: devices_pb.GetDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
        sensors_service: FromDishka[SensorsService],
        actuators_service: FromDishka[ActuatorsService],
    ) -> devices_pb.GetDeviceResponse:
        logger.info("GetDevice called for device: %s", request.device_id)
        try:
            device = await devices_service.get_device(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            sensors = await sensors_service.list_by_device_id(UUID(request.device_id))
            actuators = await actuators_service.list_by_device_id(UUID(request.device_id))
            return devices_pb.GetDeviceResponse(
                device=devices_pb.DeviceInfo(
                    device_id=str(device.id),
                    place_id=str(device.place_id),
                    name=device.name,
                    status=_STATUS_TO_PROTO.get(device.status, 0),
                    last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else "",
                    created_at=device.created_at.isoformat(),
                    updated_at=device.updated_at.isoformat(),
                    sensors=[
                        devices_pb.SensorInfo(
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
                        devices_pb.ActuatorInfo(
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
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def ListDevices(  # type: ignore[override]
        self,
        request: devices_pb.ListDevicesRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> devices_pb.ListDevicesResponse:
        logger.info("ListDevices called for place: %s", request.place_id)
        try:
            page = request.page if request.page > 0 else 1
            per_page = min(request.per_page if request.per_page > 0 else 20, 100)
            devices, total = await devices_service.list_devices(
                UUID(request.user_id), UUID(request.place_id), page, per_page
            )
            return devices_pb.ListDevicesResponse(
                devices=[
                    devices_pb.DeviceSummary(
                        device_id=str(d.id),
                        place_id=str(d.place_id),
                        name=d.name,
                        status=_STATUS_TO_PROTO.get(d.status, 0),
                        last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else "",
                    )
                    for d in devices
                ],
                total=total,
            )
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def UpdateDevice(  # type: ignore[override]
        self,
        request: devices_pb.UpdateDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> devices_pb.UpdateDeviceResponse:
        logger.info("UpdateDevice called for device: %s", request.device_id)
        try:
            device_id = await devices_service.update_device(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                request.name,
            )
            return devices_pb.UpdateDeviceResponse(device_id=device_id)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteDevice(  # type: ignore[override]
        self,
        request: devices_pb.DeleteDeviceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> devices_pb.DeleteDeviceResponse:
        logger.info("DeleteDevice called for device: %s", request.device_id)
        try:
            success = await devices_service.delete_device(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return devices_pb.DeleteDeviceResponse(success=success)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteDevicesByPlace(  # type: ignore[override]
        self,
        request: devices_pb.DeleteDevicesByPlaceRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> devices_pb.DeleteDevicesByPlaceResponse:
        logger.info("DeleteDevicesByPlace called for place: %s", request.place_id)
        try:
            deleted_count, device_ids = await devices_service.delete_devices_by_place(
                UUID(request.place_id)
            )
            return devices_pb.DeleteDevicesByPlaceResponse(
                success=True, deleted_count=deleted_count, device_ids=device_ids
            )
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def RegenerateDeviceToken(  # type: ignore[override]
        self,
        request: devices_pb.RegenerateDeviceTokenRequest,
        context: grpc.aio.ServicerContext,
        devices_service: FromDishka[DevicesService],
    ) -> devices_pb.RegenerateDeviceTokenResponse:
        logger.info("RegenerateDeviceToken called for device: %s", request.device_id)
        try:
            token = await devices_service.regenerate_token(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return devices_pb.RegenerateDeviceTokenResponse(token=token)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- Sensors ---

    @inject
    async def CreateSensor(  # type: ignore[override]
        self,
        request: devices_pb.CreateSensorRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.CreateSensorResponse:
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
            return devices_pb.CreateSensorResponse(sensor_id=sensor_id)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise
        except AlreadyExistsError as e:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
            raise

    @inject
    async def ListSensors(  # type: ignore[override]
        self,
        request: devices_pb.ListSensorsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.ListSensorsResponse:
        logger.info("ListSensors called for device: %s", request.device_id)
        try:
            sensors = await sensors_service.list_sensors(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return devices_pb.ListSensorsResponse(
                sensors=[
                    devices_pb.SensorInfo(
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
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def UpdateSensor(  # type: ignore[override]
        self,
        request: devices_pb.UpdateSensorRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.UpdateSensorResponse:
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
            return devices_pb.UpdateSensorResponse(sensor_id=sensor_id)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteSensor(  # type: ignore[override]
        self,
        request: devices_pb.DeleteSensorRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.DeleteSensorResponse:
        logger.info("DeleteSensor called for sensor: %s", request.sensor_id)
        try:
            success = await sensors_service.delete_sensor(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
            )
            return devices_pb.DeleteSensorResponse(success=success)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- Thresholds ---

    @inject
    async def SetThreshold(  # type: ignore[override]
        self,
        request: devices_pb.SetThresholdRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.SetThresholdResponse:
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
            return devices_pb.SetThresholdResponse(threshold_id=threshold_id)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def ListThresholds(  # type: ignore[override]
        self,
        request: devices_pb.ListThresholdsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.ListThresholdsResponse:
        logger.info("ListThresholds called for sensor: %s", request.sensor_id)
        try:
            thresholds = await sensors_service.list_thresholds(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
            )
            return devices_pb.ListThresholdsResponse(
                thresholds=[
                    devices_pb.ThresholdInfo(
                        threshold_id=str(t.id),
                        sensor_id=str(t.sensor_id),
                        type=_THRESHOLD_TYPE_TO_PROTO.get(t.type, 0),
                        value=t.value,
                        severity=_SEVERITY_TO_PROTO.get(t.severity, 0),
                    )
                    for t in thresholds
                ]
            )
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteThreshold(  # type: ignore[override]
        self,
        request: devices_pb.DeleteThresholdRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.DeleteThresholdResponse:
        logger.info("DeleteThreshold called for threshold: %s", request.threshold_id)
        try:
            success = await sensors_service.delete_threshold(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.sensor_id),
                UUID(request.threshold_id),
            )
            return devices_pb.DeleteThresholdResponse(success=success)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def GetSensorThresholds(  # type: ignore[override]
        self,
        request: devices_pb.GetSensorThresholdsRequest,
        context: grpc.aio.ServicerContext,
        sensors_service: FromDishka[SensorsService],
    ) -> devices_pb.GetSensorThresholdsResponse:
        logger.info("GetSensorThresholds called for sensor: %s", request.sensor_id)
        thresholds = await sensors_service.get_sensor_thresholds(UUID(request.sensor_id))
        return devices_pb.GetSensorThresholdsResponse(
            thresholds=[
                devices_pb.ThresholdInfo(
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
        request: devices_pb.CreateActuatorRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> devices_pb.CreateActuatorResponse:
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
                request.min_value if request.min_value is not None else None,
                request.max_value if request.max_value is not None else None,
                request.step if request.step is not None else None,
                list(request.enum_options) or None,
            )
            return devices_pb.CreateActuatorResponse(actuator_id=actuator_id)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise
        except AlreadyExistsError as e:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
            raise

    @inject
    async def ListActuators(  # type: ignore[override]
        self,
        request: devices_pb.ListActuatorsRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> devices_pb.ListActuatorsResponse:
        logger.info("ListActuators called for device: %s", request.device_id)
        try:
            actuators = await actuators_service.list_actuators(
                UUID(request.user_id), UUID(request.place_id), UUID(request.device_id)
            )
            return devices_pb.ListActuatorsResponse(
                actuators=[
                    devices_pb.ActuatorInfo(
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
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def UpdateActuator(  # type: ignore[override]
        self,
        request: devices_pb.UpdateActuatorRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> devices_pb.UpdateActuatorResponse:
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
            return devices_pb.UpdateActuatorResponse(actuator_id=actuator_id)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    @inject
    async def DeleteActuator(  # type: ignore[override]
        self,
        request: devices_pb.DeleteActuatorRequest,
        context: grpc.aio.ServicerContext,
        actuators_service: FromDishka[ActuatorsService],
    ) -> devices_pb.DeleteActuatorResponse:
        logger.info("DeleteActuator called for actuator: %s", request.actuator_id)
        try:
            success = await actuators_service.delete_actuator(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                UUID(request.actuator_id),
            )
            return devices_pb.DeleteActuatorResponse(success=success)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise

    # --- Commands ---

    @inject
    async def SendCommand(  # type: ignore[override]
        self,
        request: devices_pb.SendCommandRequest,
        context: grpc.aio.ServicerContext,
        commands_service: FromDishka[CommandsService],
    ) -> devices_pb.SendCommandResponse:
        logger.info("SendCommand called for device: %s", request.device_id)
        try:
            success = await commands_service.send_command(
                UUID(request.user_id),
                UUID(request.place_id),
                UUID(request.device_id),
                request.actuator_key,
                request.value,
            )
            return devices_pb.SendCommandResponse(success=success)
        except PermissionDeniedError as e:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            raise
        except NotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            raise
        except InvalidValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            raise

    # --- MQTT auth ---

    @inject
    async def AuthenticateDevice(  # type: ignore[override]
        self,
        request: devices_pb.AuthenticateDeviceRequest,
        context: grpc.aio.ServicerContext,
        mqtt_auth_service: FromDishka[MqttAuthService],
    ) -> devices_pb.AuthenticateDeviceResponse:
        logger.info("AuthenticateDevice called for: %s", request.username)
        allow = await mqtt_auth_service.authenticate(request.username, request.password)
        return devices_pb.AuthenticateDeviceResponse(allow=allow)

    @inject
    async def CheckDeviceAcl(  # type: ignore[override]
        self,
        request: devices_pb.CheckDeviceAclRequest,
        context: grpc.aio.ServicerContext,
        mqtt_auth_service: FromDishka[MqttAuthService],
    ) -> devices_pb.CheckDeviceAclResponse:
        logger.info("CheckDeviceAcl called for: %s topic=%s", request.username, request.topic)
        allow = await mqtt_auth_service.check_acl(request.username, request.topic, request.action)
        return devices_pb.CheckDeviceAclResponse(allow=allow)

    # --- MQTT credentials ---

    @inject
    async def GenerateMqttCredentials(  # type: ignore[override]
        self,
        request: devices_pb.GenerateMqttCredentialsRequest,
        context: grpc.aio.ServicerContext,
        mqtt_auth_service: FromDishka[MqttAuthService],
    ) -> devices_pb.GenerateMqttCredentialsResponse:
        logger.info("GenerateMqttCredentials called for user: %s", request.user_id)
        username, password, expires_at = await mqtt_auth_service.generate_mqtt_credentials(
            UUID(request.user_id)
        )
        return devices_pb.GenerateMqttCredentialsResponse(
            username=username, password=password, expires_at=expires_at
        )
