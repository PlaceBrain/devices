# Devices Service

- **Порт:** 50053
- **БД:** devices_db (PostgreSQL), Redis
- MQTT-клиент для отправки команд на устройства
- Зависит от places (проверка ролей), MQTT-брокера и Redis

## Структура

```
src/
├── main.py
├── core/
│   ├── config.py                    # Pydantic Settings
│   ├── authorization.py             # check_write_permission, check_read_permission (shared)
│   ├── exceptions.py                # NotFoundError, AlreadyExistsError, PermissionDeniedError, InvalidValueError
│   ├── roles.py                     # WRITE_ROLES (из proto-констант)
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
│   └── devices.py                   # gRPC DevicesHandler (все RPC-методы)
├── services/
│   ├── devices.py                   # CRUD устройств, статус, token
│   ├── sensors.py                   # CRUD сенсоров, пороги
│   ├── actuators.py                 # CRUD актуаторов
│   ├── commands.py                  # Отправка команд через MQTT
│   └── mqtt_auth.py                 # MQTT аутентификация и ACL
└── infra/db/
    ├── helper.py
    ├── uow.py
    ├── models/                      # Device, Sensor, Actuator, SensorThreshold
    └── repositories/
```

## Protobuf-импорты

```python
from placebrain_contracts import devices_pb2 as devices_pb
```

## Обработка ошибок

Типизированные исключения из `core/exceptions.py`:

| Exception              | gRPC StatusCode      |
|------------------------|----------------------|
| `NotFoundError`        | `NOT_FOUND`          |
| `AlreadyExistsError`   | `ALREADY_EXISTS`     |
| `PermissionDeniedError`| `PERMISSION_DENIED`  |
| `InvalidValueError`    | `INVALID_ARGUMENT`   |

## Авторизация

Shared-функции `check_write_permission` и `check_read_permission` в `core/authorization.py`. Проверяют роль через gRPC-вызов к places-сервису.

## UnitOfWork

Управляется через DI teardown (yield-based). Сервисы работают с репозиториями напрямую без `async with self.uow:`.

## Модели

- Device, Sensor, Actuator, SensorThreshold (PostgreSQL)
- ValueType: NUMBER, BOOLEAN (для сенсоров)
- ActuatorValueType: NUMBER, BOOLEAN, ENUM
- ThresholdType: MIN, MAX; Severity: WARNING, CRITICAL

## Redis

- MQTT credentials для фронтенд-пользователей: `mqtt:cred:user:{user_id}` → Hash
- TTL: 24 часа, инвалидация через `InvalidateMqttCredentials`

## MQTT авторизация

- Usernames: `device:{id}` / `user:{id}` / `collector`
- Устройства — постоянный токен (bcrypt-хеш), пользователи — временные credentials из Redis

## bcrypt

Все вызовы `hashpw`/`checkpw` вынесены в `loop.run_in_executor()`.

## Пагинация

- `ListDevices` — `page`/`per_page` в proto, `total` в response
- Остальные list-эндпоинты без пагинации

## Internal методы (без auth)

- GetAllThresholds, GetSensorThresholds, UpdateDeviceStatus, InvalidateMqttCredentials, DeleteDevicesByPlace
