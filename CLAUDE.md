# Devices Service

- **Port:** 50053
- **DB:** devices_db (PostgreSQL), Redis
- **Kafka:** consumer (`places.events`, `telemetry.status`) + producer (`devices.events`)
- MQTT client for sending commands to devices

## Structure

```
src/
├── main.py
├── core/
│   ├── config.py                    # Pydantic Settings
│   ├── authorization.py             # check_write_permission, check_read_permission (shared)
│   ├── exceptions.py                # NotFoundError, AlreadyExistsError, PermissionDeniedError, InvalidValueError
│   ├── roles.py                     # WRITE_ROLES (from proto constants)
│   └── types.py                     # IDType, UNSET sentinel
├── dependencies/
│   ├── config.py
│   ├── db.py                        # DatabaseHelper (APP), UoW (REQUEST, yield-based)
│   ├── devices.py                   # DevicesService, SensorsService, ActuatorsService, CommandsService
│   ├── kafka.py                     # KafkaBroker (APP scope)
│   ├── mqtt.py                      # MQTT client (APP)
│   ├── mqtt_auth.py                 # MqttAuthService (REQUEST)
│   └── redis.py                     # Redis client (APP)
├── handlers/
│   └── devices.py                   # gRPC DevicesHandler (all RPC methods)
├── services/
│   ├── devices.py                   # CRUD devices, status, token
│   ├── sensors.py                   # CRUD sensors, thresholds
│   ├── actuators.py                 # CRUD actuators
│   ├── commands.py                  # Sending commands via MQTT
│   ├── mqtt_auth.py                 # MQTT authentication and ACL
│   └── role_cache.py                # RoleCacheService (Redis-based role cache)
└── infra/
    ├── db/
    │   ├── helper.py
    │   ├── uow.py
    │   ├── models/                  # Device, Sensor, Actuator, SensorThreshold
    │   └── repositories/
    └── broker/
        └── routes.py                # KafkaRouter with typed subscribers (FromDishka DI)
```

## Protobuf Imports

```python
from placebrain_contracts import devices_pb2 as devices_pb
```

## Error Handling

Typed exceptions from `core/exceptions.py`:

| Exception              | gRPC StatusCode      |
|------------------------|----------------------|
| `NotFoundError`        | `NOT_FOUND`          |
| `AlreadyExistsError`   | `ALREADY_EXISTS`     |
| `PermissionDeniedError`| `PERMISSION_DENIED`  |
| `InvalidValueError`    | `INVALID_ARGUMENT`   |

## Authorization

Shared functions `check_write_permission` and `check_read_permission` in `core/authorization.py`. They verify roles via `RoleCacheService` (Redis-backed). The cache is populated by Kafka events from places service — no synchronous gRPC calls to places.

**Device validation helper:** Services that check device existence + place ownership use `_get_device_or_fail(device_id, place_id)` — do not inline this check.

## UnitOfWork

Managed via DI teardown (yield-based). Services work with repositories directly without `async with self.uow:`.

## Models

- Device, Sensor, Actuator, SensorThreshold (PostgreSQL)
- ValueType: NUMBER, BOOLEAN (for sensors)
- ActuatorValueType: NUMBER, BOOLEAN, ENUM
- ThresholdType: MIN, MAX; Severity: WARNING, CRITICAL

## Redis

- **Role cache:** `place_roles:{place_id}` → Hash (user_id → role), `user_places:{user_id}` → Set of place_ids. Populated via Kafka events from places service
- **MQTT credentials:** `mqtt:cred:user:{user_id}` → Hash, TTL 24h, invalidation via Kafka events (`MemberRemoved`, `PlaceDeleted`)
- **mypy:** `redis` module is ignored in mypy config (`follow_imports = "skip"`) — redis-py has incomplete type stubs

## MQTT Authorization

- Usernames: `device:{id}` / `user:{id}` / `collector`
- Devices — persistent token (bcrypt hash), users — temporary credentials from Redis

## bcrypt

All `hashpw`/`checkpw` calls are offloaded to `loop.run_in_executor()`.

## Pagination

- `ListDevices` — `page`/`per_page` in proto, `total` in response
- Other list endpoints have no pagination

## Internal Methods (no auth)

- GetAllThresholds, GetSensorThresholds, UpdateDeviceStatus, InvalidateMqttCredentials, DeleteDevicesByPlace

## Kafka Events

Subscribers in `src/infra/broker/routes.py` via `KafkaRouter` + `FromDishka[]`. One topic per event type.

**Consumes** (group: `devices-service`):

| Topic | Event | Action |
|-------|-------|--------|
| `places.member.added` | `MemberAdded` | Update role cache |
| `places.member.removed` | `MemberRemoved` | Remove role + invalidate MQTT credentials |
| `places.member.role-changed` | `MemberRoleChanged` | Update role cache |
| `places.place.deleted` | `PlaceDeleted` | Remove roles, delete devices, invalidate MQTT creds, publish `DevicesBulkDeleted` via publisher chain |
| `telemetry.status` | `EmqxStatusMessage` | Device status updates (online/offline) |

**Produces:**

| Topic | Event | Trigger |
|-------|-------|---------|
| `devices.device.bulk-deleted` | `DevicesBulkDeleted` | Publisher chain from `on_place_deleted` |
| `devices.threshold.created` | `ThresholdCreated` | `SensorsService.set_threshold()` |
| `devices.threshold.deleted` | `ThresholdDeleted` | `SensorsService.delete_threshold()` |
| `devices.device.deleted` | `DeviceDeleted` | `DevicesService.delete_device()` |
