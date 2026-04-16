import logging
from uuid import UUID

from dishka_faststream import FromDishka
from faststream.kafka import KafkaBroker, KafkaRouter
from placebrain_contracts.events import (
    TOPIC_DEVICES_BULK_DELETED,
    TOPIC_MEMBER_ADDED,
    TOPIC_MEMBER_REMOVED,
    TOPIC_MEMBER_ROLE_CHANGED,
    TOPIC_PLACE_DELETED,
    TOPIC_TELEMETRY_STATUS,
    DevicesBulkDeleted,
    EmqxStatusMessage,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
    PlaceDeleted,
)

from src.infra.db.models.device import DeviceStatusEnum
from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)
router = KafkaRouter()


@router.subscriber(TOPIC_MEMBER_ADDED, group_id="devices-service")
async def on_member_added(
    event: MemberAdded,
    role_cache: FromDishka[RoleCacheService],
) -> None:
    await role_cache.set_role(event.place_id, event.user_id, event.role)
    logger.info("Role cached: %s in %s = %s", event.user_id, event.place_id, event.role)


@router.subscriber(TOPIC_MEMBER_REMOVED, group_id="devices-service")
async def on_member_removed(
    event: MemberRemoved,
    role_cache: FromDishka[RoleCacheService],
    mqtt_auth: FromDishka[MqttAuthService],
) -> None:
    await role_cache.remove_role(event.place_id, event.user_id)
    await mqtt_auth.invalidate_credentials([str(event.user_id)])
    logger.info(
        "Role removed and MQTT creds invalidated: %s from %s",
        event.user_id,
        event.place_id,
    )


@router.subscriber(TOPIC_MEMBER_ROLE_CHANGED, group_id="devices-service")
async def on_member_role_changed(
    event: MemberRoleChanged,
    role_cache: FromDishka[RoleCacheService],
) -> None:
    await role_cache.set_role(event.place_id, event.user_id, event.role)
    logger.info("Role cache updated: %s in %s = %s", event.user_id, event.place_id, event.role)


@router.subscriber(TOPIC_PLACE_DELETED, group_id="devices-service")
async def on_place_deleted(
    event: PlaceDeleted,
    role_cache: FromDishka[RoleCacheService],
    devices_service: FromDishka[DevicesService],
    mqtt_auth: FromDishka[MqttAuthService],
    broker: FromDishka[KafkaBroker],
) -> None:
    member_ids = [str(m) for m in event.member_ids]
    await role_cache.remove_place(event.place_id)
    deleted_count, device_ids = await devices_service.delete_devices_by_place(event.place_id)
    await mqtt_auth.invalidate_credentials(member_ids)
    if device_ids:
        await broker.publish(
            DevicesBulkDeleted(device_ids=[UUID(d) for d in device_ids]),
            topic=TOPIC_DEVICES_BULK_DELETED,
            key=str(event.place_id).encode(),
        )
    logger.info(
        "Place %s deleted: %d devices removed, %d members invalidated",
        event.place_id,
        deleted_count,
        len(member_ids),
    )


@router.subscriber(TOPIC_TELEMETRY_STATUS, group_id="devices-service")
async def on_device_status(
    msg: EmqxStatusMessage,
    devices_service: FromDishka[DevicesService],
) -> None:
    device_id_str = msg.extract_device_id()
    try:
        device_id = UUID(device_id_str)
        status = DeviceStatusEnum(msg.payload.status)
        await devices_service.update_device_status(device_id, status)
        logger.debug("Device %s status updated to %s", device_id, status)
    except (ValueError, KeyError) as e:
        logger.warning("Invalid status message: %s, error: %s", msg, e)
