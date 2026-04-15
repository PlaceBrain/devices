import logging
from typing import Any
from uuid import UUID

from faststream.kafka import KafkaBroker
from placebrain_contracts.events import (
    BaseEvent,
    DevicesBulkDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
    PlaceDeleted,
)
from pydantic import ValidationError

from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)

DEVICES_EVENTS_TOPIC = "devices.events"

PLACES_EVENT_MAP: dict[str, type[BaseEvent]] = {
    "member.added": MemberAdded,
    "member.removed": MemberRemoved,
    "member.role_changed": MemberRoleChanged,
    "place.deleted": PlaceDeleted,
}


async def handle_places_event(
    data: dict[str, Any],
    role_cache: RoleCacheService,
    devices_service: DevicesService,
    mqtt_auth_service: MqttAuthService,
    broker: KafkaBroker,
) -> None:
    event_type = data.get("event_type")
    model_cls = PLACES_EVENT_MAP.get(event_type)  # type: ignore[arg-type]
    if not model_cls:
        logger.warning("Unknown places event type: %s", event_type)
        return

    try:
        event = model_cls.model_validate(data)
    except ValidationError:
        logger.exception("Invalid places event payload: %s", event_type)
        return

    if isinstance(event, MemberAdded):
        await role_cache.set_role(event.place_id, event.user_id, event.role)
        logger.info("Role cache updated: %s in %s = %s", event.user_id, event.place_id, event.role)

    elif isinstance(event, MemberRemoved):
        await role_cache.remove_role(event.place_id, event.user_id)
        await mqtt_auth_service.invalidate_credentials([str(event.user_id)])
        logger.info(
            "Role removed and MQTT creds invalidated: %s from %s",
            event.user_id,
            event.place_id,
        )

    elif isinstance(event, MemberRoleChanged):
        await role_cache.set_role(event.place_id, event.user_id, event.role)
        logger.info("Role cache updated: %s in %s = %s", event.user_id, event.place_id, event.role)

    elif isinstance(event, PlaceDeleted):
        member_ids = [str(m) for m in event.member_ids]
        await role_cache.remove_place(event.place_id)
        deleted_count, device_ids = await devices_service.delete_devices_by_place(event.place_id)
        await mqtt_auth_service.invalidate_credentials(member_ids)
        if device_ids:
            bulk_event = DevicesBulkDeleted(device_ids=[UUID(d) for d in device_ids])
            await broker.publish(
                bulk_event.model_dump(mode="json"),
                topic=DEVICES_EVENTS_TOPIC,
                key=str(event.place_id).encode(),
            )
        logger.info(
            "Place %s deleted: %d devices removed, %d members invalidated",
            event.place_id,
            deleted_count,
            len(member_ids),
        )


async def handle_device_status(
    data: dict[str, Any],
    devices_service: DevicesService,
) -> None:
    topic = data.get("topic", "")
    payload = data.get("payload", data)

    if isinstance(payload, str):
        import orjson

        payload = orjson.loads(payload)

    parts = topic.split("/") if isinstance(topic, str) and "/" in topic else []
    if len(parts) >= 5:
        device_id_str = parts[3]
    else:
        device_id_str = payload.get("device_id", "")

    if not device_id_str:
        logger.warning("Cannot extract device_id from status message: %s", data)
        return

    status_str = payload.get("status", "")
    if not status_str:
        logger.warning("No status in message: %s", data)
        return

    from src.infra.db.models.device import DeviceStatusEnum

    try:
        device_id = UUID(device_id_str)
        status = DeviceStatusEnum(status_str)
        await devices_service.update_device_status(device_id, status)
        logger.debug("Device %s status updated to %s", device_id, status_str)
    except (ValueError, KeyError) as e:
        logger.warning("Invalid status message: %s, error: %s", data, e)
