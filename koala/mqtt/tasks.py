import json
import logging
import time
from typing import Any, Dict

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, queue='iot_default_q')
def process_iot_message(self, topic: str, message_data: dict):
    """
    統一的IoT消息處理入口
    根據message_type路由到不同的處理函數
    """
    try:
        message_type = message_data.get('message_type')
        logger.info(f"Processing {message_type} message from {topic}")

        # 根據message_type路由到對應處理器
        if message_type == 'telemetry':
            return process_telemetry_data.delay(message_data)
        elif message_type == 'fleet':
            return process_fleet_data.delay(message_data)
        elif message_type == 'sport':
            return process_sport_data.delay(message_data)
        else:
            logger.warning(f"Unknown message_type: {message_type}")
            return process_unknown_message.delay(topic, message_data)

    except Exception as exc:
        logger.error(f"Error processing message from {topic}: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying task in {settings.CELERY_MQTT_CONFIG['RETRY_DELAY']} seconds..."
            )
            raise self.retry(
                exc=exc, countdown=settings.CELERY_MQTT_CONFIG['RETRY_DELAY']
            )
        else:
            logger.error(f"Max retries exceeded for topic {topic}")
            raise


@shared_task(queue='iot_default_q')
def process_telemetry_data(message_data: dict):
    """
    處理遙測數據
    包含位置、速度、電池等資訊
    """
    try:
        bike_id = message_data.get('bike_id')
        data = message_data.get('data', {})

        logger.info(f"Processing telemetry data for bike {bike_id}")
        logger.info(f"Telemetry data: {data}")

        logger.info(f"Successfully processed telemetry for bike {bike_id}")
        return f"Processed telemetry for bike {bike_id}"

    except Exception as e:
        logger.error(f"Error processing telemetry data: {e}")
        raise


@shared_task(queue='iot_default_q')
def process_fleet_data(message_data: dict):
    """
    處理車隊管理數據
    包含維護狀態、可用性等資訊
    """
    try:
        bike_id = message_data.get('bike_id')
        data = message_data.get('data', {})

        logger.info(f"Processing fleet data for bike {bike_id}")
        logger.info(f"Fleet data: {data}")

        logger.info(f"Successfully processed fleet data for bike {bike_id}")
        return f"Processed fleet data for bike {bike_id}"

    except Exception as e:
        logger.error(f"Error processing fleet data: {e}")
        raise


@shared_task(queue='iot_default_q')
def process_sport_data(message_data: dict):
    """
    處理運動數據
    包含卡路里、距離、運動時間等
    """
    try:
        bike_id = message_data.get('bike_id')
        data = message_data.get('data', {})

        logger.info(f"Processing sport data for bike {bike_id}")
        logger.info(f"Sport data: {data}")

        logger.info(f"Successfully processed sport data for bike {bike_id}")
        return f"Processed sport data for bike {bike_id}"

    except Exception as e:
        logger.error(f"Error processing sport data: {e}")
        raise


@shared_task(queue='iot_default_q')
def process_unknown_message(topic: str, message_data: dict):
    """
    處理未知類型的消息
    """
    try:
        logger.warning(f"Processing unknown message type from topic: {topic}")

        logger.info(f"Logged unknown message from topic: {topic}")
        return f"Logged unknown message from {topic}"

    except Exception as e:
        logger.error(f"Error processing unknown message: {e}")
        raise
