import logging

from celery import shared_task
from django.conf import settings

from telemetry.constants import IoTConstants

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
        if message_type == IoTConstants.MESSAGE_TYPE_TELEMETRY:
            from telemetry.tasks import process_telemetry_data

            return process_telemetry_data.delay(message_data)
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
