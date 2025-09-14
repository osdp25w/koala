import logging

from bike.models import BikeErrorLog
from websocket.services import BaseNotificationService

logger = logging.getLogger(__name__)


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
