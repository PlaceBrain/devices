# Devices Service

- **Port:** 50053
- **DB:** devices_db (PostgreSQL), Redis
- MQTT client for sending commands to devices
- Depends on places (role checks), MQTT broker, and Redis

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
│   ├── grpc.py                      # PlacesServiceStub (APP)
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
│   └── mqtt_auth.py                 # MQTT authentication and ACL
└── infra/db/
    ├── helper.py
    ├── uow.py
    ├── models/                      # Device, Sensor, Actuator, SensorThreshold
    └── repositories/
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

Shared functions `check_write_permission` and `check_read_permission` in `core/authorization.py`. They verify roles via gRPC call to the places service.

## UnitOfWork

Managed via DI teardown (yield-based). Services work with repositories directly without `async with self.uow:`.

## Models

- Device, Sensor, Actuator, SensorThreshold (PostgreSQL)
- ValueType: NUMBER, BOOLEAN (for sensors)
- ActuatorValueType: NUMBER, BOOLEAN, ENUM
- ThresholdType: MIN, MAX; Severity: WARNING, CRITICAL

## Redis

- MQTT credentials for frontend users: `mqtt:cred:user:{user_id}` → Hash
- TTL: 24 hours, invalidation via `InvalidateMqttCredentials`

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
