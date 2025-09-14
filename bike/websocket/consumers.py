import json
import logging

from channels.db import database_sync_to_async

from websocket.consumers import BaseNotificationConsumer

logger = logging.getLogger(__name__)


class BikeErrorLogNotificationConsumer(BaseNotificationConsumer):
    """
    處理 Bike 錯誤日誌通知的 WebSocket 連接
    只允許 Staff 用戶連接，用於接收錯誤提醒
    """

    GROUP_NAMES = ['bike_error_log_group']

    async def setup(self):
        """
        設定 Bike 錯誤日誌 Consumer
        """
        self.staff = await database_sync_to_async(lambda: self.user.profile)()
        self.staff_id = self.staff.id

        # 設定要加入的群組
        self.group_names = self.GROUP_NAMES

        logger.info(f"Staff {self.staff_id} setup for bike error log notifications")

    # === Channel 事件處理 ===

    async def bike_error_log_notification(self, event):
        """
        處理錯誤日誌提醒事件，推送給前端
        """
        try:
            # 發送簡化的錯誤提醒給前端
            await self.send(
                text_data=json.dumps(
                    {'type': 'bike_error_log_notification', 'data': event['data']},
                    ensure_ascii=False,
                )
            )

            logger.debug(
                f"Sent error log notification to staff {self.staff_id}: bike {event['data']['bike_id']}"
            )

        except Exception as e:
            logger.error(f"Error sending bike error log notification: {e}")
