import logging
from datetime import timedelta
from typing import List

from celery import shared_task
from django.db.models import Max, Q
from django.utils import timezone

from bike.models import BikeRealtimeStatus
from bike.services import BikeRealtimeStatusTelemetrySyncer
from telemetry.constants import IoTConstants
from telemetry.models import TelemetryRecord

logger = logging.getLogger(__name__)


@shared_task(queue='bike_realtime_status_q')
def sync_bike_realtime_status():
    """
    同步車輛即時狀態
    每10秒執行，從最近5分鐘的遙測記錄中更新車輛位置和基本狀態
    """
    try:
        # 使用統一的車輛即時狀態遙測同步器
        result = BikeRealtimeStatusTelemetrySyncer.sync_from_recent_telemetry(
            time_window_minutes=5
        )

        if result['success']:
            return result['message']
        else:
            logger.error(f"Sync failed: {result['error']}")
            raise Exception(result['error'])

    except Exception as e:
        logger.error(f"Error syncing bike realtime status: {e}")
        raise


@shared_task(queue='bike_error_log_q')
def handle_bike_error_log(error_data: dict):
    """
    異步處理車輛錯誤日誌並批次建立已讀狀態

    Args:
        error_data: {
            'bike_id': str,
            'code': str,  # 錯誤代碼
            'level': str,  # 'info', 'warning', 'critical'
            'title': str,
            'detail': str,
            'telemetry_device_imei': str (optional),  # 設備 IMEI
            'telemetry_record_snapshot': dict (optional),
            'extra_context': dict (optional),
        }
    """
    try:
        from account.models import Staff
        from bike.models import BikeErrorLog, BikeErrorLogStatus, BikeInfo
        from telemetry.models import TelemetryDevice

        # 獲取車輛信息
        bike = BikeInfo.objects.get(bike_id=error_data['bike_id'])

        # 準備創建參數
        create_params = {
            'bike': bike,
            'code': error_data['code'],
            'level': error_data['level'],
            'title': error_data['title'],
            'detail': error_data['detail'],
        }

        # 處理可選字段
        if error_data.get('telemetry_device_imei'):
            try:
                create_params['telemetry_device'] = TelemetryDevice.objects.get(
                    IMEI=error_data['telemetry_device_imei']
                )
            except TelemetryDevice.DoesNotExist:
                logger.warning(
                    f"TelemetryDevice not found with IMEI: {error_data['telemetry_device_imei']}"
                )
                # 繼續處理，但不關聯設備

        if error_data.get('telemetry_record_snapshot'):
            create_params['telemetry_record_snapshot'] = error_data[
                'telemetry_record_snapshot'
            ]

        if error_data.get('extra_context'):
            create_params['extra_context'] = error_data['extra_context']

        # 創建錯誤日誌
        bike_error_log = BikeErrorLog.objects.create(**create_params)

        # 批次為所有 staff 創建已讀狀態記錄
        active_staff = Staff.objects.filter(is_active=True)
        read_statuses = [
            BikeErrorLogStatus(
                error_log=bike_error_log, staff=staff, is_read=False, read_at=None
            )
            for staff in active_staff
        ]

        BikeErrorLogStatus.objects.bulk_create(
            read_statuses, ignore_conflicts=True  # 避免重複創建
        )

        logger.info(
            f"Created bike error log {bike_error_log.id} with {len(read_statuses)} read statuses"
        )

    except BikeInfo.DoesNotExist:
        logger.error(f"Bike not found: {error_data.get('bike_id')}")
    except Exception as e:
        logger.error(f"Failed to handle bike error log: {e}")
        raise
