# devices

> gRPC service for IoT devices, sensors, actuators and thresholds — the device plane of PlaceBrain.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)
![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)
![gRPC](https://img.shields.io/badge/gRPC-1.76-green.svg)
![Kafka](https://img.shields.io/badge/Kafka-4.0-black.svg)
![MQTT](https://img.shields.io/badge/MQTT-EMQX-orange.svg)

Owns the model of physical devices inside a place: a `Device` has many `Sensor`s and `Actuator`s; a sensor can have `SensorThreshold`s that trigger alerts. Also responsible for MQTT authentication: every device and every web user is authenticated by this service through EMQX webhooks.

## Role in PlaceBrain

PlaceBrain is an open-source IoT platform for smart buildings. See the [organization profile](https://github.com/PlaceBrain) for the full architecture.

- Called over gRPC by [gateway](https://github.com/PlaceBrain/gateway) for device/sensor/actuator/threshold CRUD and command dispatch.
- Called internally by EMQX (through gateway's `/api/internal/mqtt/*` webhooks) for `auth` and `acl` decisions.
- Maintains a role cache in Redis, fed by Kafka events from [places](https://github.com/PlaceBrain/places), so it never has to make a synchronous gRPC call to authorize a request.
- Publishes its own events to Kafka — [collector](https://github.com/PlaceBrain/collector) consumes them to drop readings/alerts and update threshold caches.

## Tech stack

- Python 3.14, uv
- gRPC + FastStream on aiokafka, with `dishka-faststream` for DI in subscribers
- [aiomqtt](https://github.com/sbtinstruments/aiomqtt) for command publishing
- Redis (`redis-py`) for role cache + short-lived MQTT user credentials
- Dishka DI, SQLAlchemy 2.0 async + asyncpg, Alembic migrations
- Async bcrypt via `loop.run_in_executor()` (MQTT tokens and user passwords)

## gRPC methods (port 50053)

Read: `ListDevices`, `GetDevice`, `GetSensors`, `GetActuators`, `GetSensorThresholds`, `GetLatestDeviceReadings`
Write: `CreateDevice`, `UpdateDevice`, `DeleteDevice`, `CreateSensor`, `UpdateSensor`, `DeleteSensor`, `CreateActuator`, `UpdateActuator`, `DeleteActuator`, `SetSensorThreshold`, `DeleteSensorThreshold`, `SendCommand`, `RegenerateMqttToken`
Internal (no auth, Docker-network only): `GetAllThresholds`, `UpdateDeviceStatus`, `InvalidateMqttCredentials`, `DeleteDevicesByPlace`

Proto definitions live in [placebrain-contracts](https://github.com/PlaceBrain/contracts) (`devices.proto`).

## Kafka events

Subscribers live in `src/infra/broker/routes.py` using a `KafkaRouter` and `FromDishka[]`.

**Consumes** (consumer group `devices-service`):

| Topic | Event | Action |
|---|---|---|
| `places.member.added` | `MemberAdded` | Update role cache |
| `places.member.removed` | `MemberRemoved` | Remove role + invalidate MQTT credentials |
| `places.member.role-changed` | `MemberRoleChanged` | Update role cache |
| `places.place.deleted` | `PlaceDeleted` | Drop roles, delete devices, emit `DevicesBulkDeleted` via publisher chain |
| `telemetry.status` | `EmqxStatusMessage` | Device online/offline transitions |

**Produces:**

| Topic | Event | Trigger |
|---|---|---|
| `devices.device.deleted` | `DeviceDeleted` | `DeleteDevice` |
| `devices.device.bulk-deleted` | `DevicesBulkDeleted` | publisher chain from `on_place_deleted` |
| `devices.threshold.created` | `ThresholdCreated` | `SetSensorThreshold` |
| `devices.threshold.deleted` | `ThresholdDeleted` | `DeleteSensorThreshold` |

## MQTT authorization

EMQX calls the gateway's internal webhooks, which relay to this service.

- Device usernames: `device:{device_id}` — password is a persistent token (bcrypt-hashed in Postgres).
- User usernames: `user:{user_id}` — short-lived credentials minted on demand and cached in Redis (`mqtt:cred:user:{user_id}`, TTL 24h; invalidated by `MemberRemoved` / `PlaceDeleted`).
- `collector` — internal username used by the [collector](https://github.com/PlaceBrain/collector) service.

## Local development

**Full stack (recommended):** clone [infra](https://github.com/PlaceBrain/infra) and run `make dev`.

**Service-only mode:**

```bash
uv sync
cp .env.example .env          # set DATABASE__URL, REDIS__URL, KAFKA__URL, MQTT__URL
uv run alembic upgrade head
uv run python -m src
```

Requires PostgreSQL (`devices_db`), Redis, Kafka and an MQTT broker reachable at the configured URLs.

## Environment variables

See [`.env.example`](./.env.example).

## Project layout

```
src/
├── main.py
├── core/                    Settings, shared authorization helpers, typed exceptions, role constants
├── dependencies/            Dishka providers (config, db/uow, kafka, mqtt, redis, services, mqtt_auth)
├── handlers/devices.py      gRPC DevicesHandler (all methods)
├── services/
│   ├── devices.py           CRUD devices, status, token
│   ├── sensors.py           CRUD sensors, thresholds (publishes to Kafka)
│   ├── actuators.py         CRUD actuators
│   ├── commands.py          MQTT command dispatch
│   ├── mqtt_auth.py         EMQX auth + ACL
│   └── role_cache.py        Redis + in-memory role cache
└── infra/
    ├── db/                  Models (Device, Sensor, Actuator, SensorThreshold), repositories, UoW
    └── broker/routes.py     KafkaRouter subscribers with DI
```

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
