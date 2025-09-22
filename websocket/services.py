import logging
from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class BaseNotificationService:
    """
    Base WebSocket 通知服務
    提供通用的 WebSocket 功能
    """

    @staticmethod
    def test_connection(group_name):
        """
        測試指定群組的 Channel Layer 連接是否正常

        Args:
            group_name: 要測試的群組名稱
        """
        try:
            channel_layer = get_channel_layer()

            # 發送測試消息
            test_data = {
                'message': f'WebSocket connection test for {group_name}',
                'timestamp': datetime.now().isoformat(),
            }

            async_to_sync(channel_layer.group_send)(
                group_name, {'type': 'test_message', 'data': test_data}
            )

            logger.info(
                f"WebSocket test message sent to group '{group_name}' successfully"
            )
            return True

        except Exception as e:
            logger.error(f"WebSocket test failed for group '{group_name}': {e}")
            return False

    @staticmethod
    def send_to_group(group_name, message_type, data):
        """
        通用的群組廣播方法

        Args:
            group_name: 群組名稱
            message_type: 消息類型
            data: 消息數據
        """
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                group_name, {'type': message_type, 'data': data}
            )

            logger.debug(f"Sent message to group '{group_name}': {message_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message to group '{group_name}': {e}")
            return False
