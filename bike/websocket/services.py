import logging
from typing import List

from bike.models import BikeErrorLog, BikeRealtimeStatus
from websocket.services import BaseNotificationService

logger = logging.getLogger(__name__)


class BikeRealtimeStatusWebSocketService(BaseNotificationService):
    """
    Bike 即時狀態 WebSocket 通知服務
    處理車輛即時狀態相關的即時推送
    """

    GROUP_NAME = 'bike_realtime_status_group'

    @staticmethod
    def broadcast_batch_status_update(bike_statuses: List[BikeRealtimeStatus]):
        """
        批量推送車輛狀態更新給所有連接的 Staff

        Args:
            bike_statuses: BikeRealtimeStatus 實例列表
        """
        try:
            if not bike_statuses:
                return

            status_data = []
            for status in bike_statuses:
                status_data.append(
                    {
                        'bike_id': status.bike.bike_id,
                        'lat_decimal': status.lat_decimal,
                        'lng_decimal': status.lng_decimal,
                        'soc': status.soc,
                        'vehicle_speed': status.vehicle_speed,
                        'last_seen': status.last_seen.isoformat(),
                    }
                )

            success = BikeRealtimeStatusWebSocketService.send_to_group(
                BikeRealtimeStatusWebSocketService.GROUP_NAME,
                'batch_status_update',
                status_data,
            )

            if success:
                logger.info(
                    f"Sent batch status update for {len(bike_statuses)} bikes to staff"
                )

        except Exception as e:
            logger.error(
                f"Failed to send batch status update for {len(bike_statuses)} bikes: {e}"
            )

    @staticmethod
    def test_connection():
        """
        測試 Bike 即時狀態 WebSocket 連接
        """
        return BikeRealtimeStatusWebSocketService.test_connection(
            BikeRealtimeStatusWebSocketService.GROUP_NAME
        )


class BikeErrorLogNotificationService(BaseNotificationService):
    """
    Bike 錯誤日誌 WebSocket 通知服務
    處理錯誤日誌相關的即時通知提醒
    """

    GROUP_NAME = 'bike_error_log_group'

    @staticmethod
    def send_error_log_notification(error_log):
        """
        發送錯誤日誌提醒給所有連接的 Staff
        只推送 warning 和 critical 級別的錯誤

        Args:
            error_log: BikeErrorLog 實例
        """
        try:
            if error_log.level not in [
                BikeErrorLog.LevelOptions.WARNING,
                BikeErrorLog.LevelOptions.CRITICAL,
            ]:
                logger.debug(
                    f"Skipped notification for info level error {error_log.id}"
                )
                return

            # 準備簡化的提醒資料
            notification_data = {
                'bike_id': error_log.bike_id,
                'level': error_log.level,
                'title': error_log.title,
                'detail': error_log.detail,
            }

            # 使用 Base 服務的通用方法
            success = BikeErrorLogNotificationService.send_to_group(
                BikeErrorLogNotificationService.GROUP_NAME,
                'bike_error_log_notification',
                notification_data,
            )

            if success:
                logger.info(
                    f"Sent error log notification for bike {error_log.bike_id}, level: {error_log.level}"
                )

        except Exception as e:
            logger.error(
                f"Failed to send error log notification for error {error_log.id}: {e}"
            )

    @staticmethod
    def test_connection():
        """
        測試 Bike 錯誤日誌 WebSocket 連接
        """
        return BikeErrorLogNotificationService.test_connection(
            BikeErrorLogNotificationService.GROUP_NAME
        )
