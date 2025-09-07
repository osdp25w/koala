"""
Telemetry 相關的 Celery 任務
處理遙測數據的業務邏輯
"""

import logging
from datetime import datetime
from typing import Dict

from celery import shared_task
from django.utils import timezone

from telemetry.constants import IoTConstants
from telemetry.models import TelemetryRecord
from telemetry.services import IoTRawProcessService

logger = logging.getLogger(__name__)


@shared_task(queue='iot_default_q')
def process_telemetry_data(message_data: dict):
    """
    處理遙測數據 - 將 IoT 設備格式轉換並存入資料庫
    """
    try:
        # 從 MQTT client 傳過來的格式: message_data['data'] 包含原始 IoT 數據
        iot_data = message_data.get('data', {})

        # IoT 數據格式:
        # { "ID": "867295075673978", "SQ": 1, "MSG": { ... } }
        device_id = iot_data.get('ID')
        sequence_id = iot_data.get('SQ')
        msg = iot_data.get('MSG', {})

        if not device_id or not msg:
            logger.error(f"Invalid IoT data format: missing ID or MSG")
            return 'Failed: Invalid data format'

        logger.info(
            f"Processing telemetry for device {device_id}, sequence {sequence_id}"
        )

        result = IoTRawProcessService.process_telemetry_message(
            device_id, sequence_id, msg
        )

        if result['success']:
            logger.info(f"Successfully processed telemetry for device {device_id}")
            return f"Processed telemetry for device {device_id}"
        else:
            logger.error(f"Failed to save telemetry: {result['error']}")
            raise Exception(result['error'])

    except Exception as e:
        logger.error(f"Error processing telemetry data: {e}")
        raise
