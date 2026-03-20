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

## Internal методы (без auth)

- GetAllThresholds, GetSensorThresholds, UpdateDeviceStatus
