"""
MQTT 模組 - 處理 IoT 設備與 RabbitMQ MQTT 的整合

這個模組包含：
- client.py: MQTT 客戶端核心邏輯
- tasks.py: Celery 任務處理 MQTT 訊息
"""

from .client import (
    mqtt_client,
    publish_bike_fleet_status,
    publish_bike_sport_metrics,
    publish_bike_telemetry,
    publish_message,
    subscribe_topic,
)
from .tasks import (
    process_fleet_data,
    process_iot_message,
    process_sport_data,
    process_telemetry_data,
)

__all__ = [
    'mqtt_client',
    'publish_message',
    'subscribe_topic',
    'publish_bike_telemetry',
    'publish_bike_fleet_status',
    'publish_bike_sport_metrics',
    'process_iot_message',
    'process_telemetry_data',
    'process_fleet_data',
    'process_sport_data',
]
