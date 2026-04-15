import logging
from typing import Any
from uuid import UUID

from faststream.kafka import KafkaBroker

from src.services.devices import DevicesService
from src.services.mqtt_auth import MqttAuthService
from src.services.role_cache import RoleCacheService

logger = logging.getLogger(__name__)

DEVICES_EVENTS_TOPIC = "devices.events"


async def handle_places_event(
    data: dict[str, Any],
    role_cache: RoleCacheService,
    devices_service: DevicesService,
    mqtt_auth_service: MqttAuthService,
    broker: KafkaBroker,
) -> None:
    event_type = data.get("event_type")

    if event_type == "member.added":
        place_id = UUID(data["place_id"])
        user_id = UUID(data["user_id"])
        role = data["role"]
        await role_cache.set_role(place_id, user_id, role)
        logger.info("Role cache updated: %s in %s = %s", user_id, place_id, role)

    elif event_type == "member.removed":
        place_id = UUID(data["place_id"])
        user_id = UUID(data["user_id"])
        await role_cache.remove_role(place_id, user_id)
        await mqtt_auth_service.invalidate_credentials([str(user_id)])
        logger.info("Role removed and MQTT creds invalidated: %s from %s", user_id, place_id)

    elif event_type == "member.role_changed":
        place_id = UUID(data["place_id"])
        user_id = UUID(data["user_id"])
        role = data["role"]
        await role_cache.set_role(place_id, user_id, role)
        logger.info("Role cache updated: %s in %s = %s", user_id, place_id, role)

    elif event_type == "place.deleted":
        place_id = UUID(data["place_id"])
        member_ids = [str(m) for m in data["member_ids"]]
        await role_cache.remove_place(place_id)
        deleted_count, device_ids = await devices_service.delete_devices_by_place(place_id)
        await mqtt_auth_service.invalidate_credentials(member_ids)
        if device_ids:
            await broker.publish(
                {
                    "event_type": "devices.bulk_deleted",
                    "device_ids": device_ids,
                },
                topic=DEVICES_EVENTS_TOPIC,
                key=str(place_id).encode(),
            )
        logger.info(
            "Place %s deleted: %d devices removed, %d members invalidated",
            place_id,
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
