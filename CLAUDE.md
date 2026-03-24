# Devices Service

- **Порт:** 50053
- **БД:** devices_db (PostgreSQL)
- MQTT-клиент для отправки команд на устройства
- Зависит от places (проверка ролей) и MQTT-брокера

## Модели

- Device, Sensor, Actuator, SensorThreshold, MqttCredential
- ValueType: NUMBER, BOOLEAN, ENUM (для актуаторов)
- ThresholdType: MIN, MAX; Severity: WARNING, CRITICAL

## MQTT авторизация

- Usernames: `device:{id}` / `user:{id}` / `collector`
- ACL: устройства pub telemetry/status, sub command; пользователи sub по place_ids; collector pub alerts, sub telemetry/status

## Роли и авторизация

- Константы ролей — в `src/core/roles.py` (импорт из proto). **Не хардкодить** числовые значения `{1, 2}`
- Проверка ролей через places-сервис (gRPC `GetPlace` → `user_role`)

## Internal методы (без auth)

- GetAllThresholds, GetSensorThresholds, UpdateDeviceStatus
