# Devices Service

- **Порт:** 50053
- **БД:** devices_db (PostgreSQL), Redis
- MQTT-клиент для отправки команд на устройства
- Зависит от places (проверка ролей), MQTT-брокера и Redis

## Модели

- Device, Sensor, Actuator, SensorThreshold (PostgreSQL)
- ValueType: NUMBER, BOOLEAN, ENUM (для актуаторов)
- ThresholdType: MIN, MAX; Severity: WARNING, CRITICAL

## Redis

- MQTT credentials для фронтенд-пользователей хранятся в Redis (не PostgreSQL)
- Ключ: `mqtt:cred:user:{user_id}` → Hash {username, password, password_hash, allowed_place_ids, expires_at}
- TTL: 24 часа (автоочистка)
- `password` хранится в plain-text для возврата клиенту без повторного bcrypt
- `password_hash` используется для аутентификации через EMQX webhook
- **Инвалидация:** gateway вызывает `InvalidateMqttCredentials(user_ids)` при изменении состава локаций

## MQTT авторизация

- Usernames: `device:{id}` / `user:{id}` / `collector`
- ACL: устройства pub telemetry/status, sub command; пользователи sub по place_ids; collector pub alerts, sub telemetry/status
- Устройства аутентифицируются постоянным токеном (bcrypt-хеш в таблице `devices`)
- Пользователи аутентифицируются временными credentials из Redis

## Роли и авторизация

- Константы ролей — в `src/core/roles.py` (импорт из proto). **Не хардкодить** числовые значения `{1, 2}`
- Проверка ролей через places-сервис (gRPC `GetPlace` → `user_role`)

## Пагинация

- `ListDevices` поддерживает сквозную пагинацию: `page`/`per_page` в proto request, `total` в response
- Service layer использует `BaseRepository.find(filters, limit, offset)` + `BaseRepository.count(filters)` — два SQL-запроса
- Handler валидирует параметры: page default=1, per_page default=20, max=100
- Остальные list-эндпоинты (sensors, actuators, thresholds) **без пагинации** — коллекции естественно ограничены

## Производительность

- **bcrypt:** все вызовы `hashpw`/`checkpw` вынесены в `loop.run_in_executor()` — не блокируют event loop
- **GetDevice:** одна проверка прав в хэндлере, sensors/actuators загружаются через internal-методы `list_by_device_id()` без повторной проверки

## Internal методы (без auth)

- GetAllThresholds, GetSensorThresholds, UpdateDeviceStatus, InvalidateMqttCredentials, DeleteDevicesByPlace
