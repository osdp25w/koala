import asyncio
import json
import logging
from datetime import timedelta
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, UntypedToken

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket 基礎 Consumer，處理通用邏輯：
    - JWT 認證
    - 連接管理
    - 錯誤處理
    子類需要實作 post_authenticate() 方法處理業務邏輯
    """

    async def connect(self):
        """
        處理 WebSocket 連接
        1. 驗證 JWT token
        2. 呼叫子類的 post_authenticate
        3. 接受連接
        """
        try:
            # 1. 獲取並驗證 token
            token = self.get_token_from_query()
            if not token:
                logger.warning('WebSocket connection rejected: No token provided')
                await self.close(code=4001)  # Unauthorized
                return

            # 2. 驗證 token 並獲取用戶
            user = await self.authenticate_token(token)
            if not user or user.is_anonymous:
                logger.warning('WebSocket connection rejected: Invalid token')
                await self.close(code=4001)  # Unauthorized
                return

            # 3. 保存用戶資訊
            self.user = user
            self.user_id = user.id

            # 4. 呼叫子類的認證後處理
            await self.post_authenticate()

            # 5. 接受連接
            await self.accept()

            # 6. 初始化心跳機制
            self.last_pong = timezone.now()
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

            logger.info(f"WebSocket connected: User {self.user_id} ({user.username})")

        except Exception as e:
            logger.error(f"Error in WebSocket connect: {e}")
            await self.close(code=4000)  # General error

    async def disconnect(self, close_code):
        """
        處理 WebSocket 斷線
        子類可以覆寫 pre_disconnect() 來處理清理邏輯
        """
        try:
            # 取消心跳任務
            if hasattr(self, 'heartbeat_task'):
                self.heartbeat_task.cancel()

            # 呼叫子類的斷線前處理
            await self.pre_disconnect()

            user_info = getattr(self, 'user_id', 'unknown')
            logger.info(f"WebSocket disconnected: User {user_info}, code: {close_code}")

        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {e}")

    async def receive(self, text_data):
        """
        處理來自客戶端的消息
        處理心跳 pong 和其他消息
        """
        try:
            data = json.loads(text_data)

            # 處理心跳 pong
            if data.get('type') == 'pong':
                self.last_pong = timezone.now()
                logger.debug(f"Received pong from user {self.user_id}")
                return

            # 其他消息交給子類處理
            await self.handle_message(data)

        except json.JSONDecodeError:
            logger.error('Invalid JSON received from WebSocket client')
            await self.send_error('Invalid JSON format')
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            await self.send_error('Message processing failed')

    # === 子類需要實作的方法 ===

    async def post_authenticate(self):
        """
        認證成功後的處理邏輯
        1. 呼叫子類的 setup() 方法
        2. 自動加入子類定義的群組
        """
        try:
            # 讓子類進行設定 (設定 group_names, 其他初始化等)
            await self.setup()

            # 自動加入所有定義的群組
            if hasattr(self, 'group_names'):
                for group_name in self.group_names:
                    await self.channel_layer.group_add(group_name, self.channel_name)
                    logger.debug(f"User {self.user_id} joined group: {group_name}")

        except Exception as e:
            logger.error(f"Error in post_authenticate: {e}")
            await self.close(code=4000)

    async def pre_disconnect(self):
        """
        斷線前的清理邏輯
        1. 自動離開所有群組
        2. 呼叫子類的 cleanup() 方法
        """
        try:
            # 自動離開所有群組
            if hasattr(self, 'group_names'):
                for group_name in self.group_names:
                    await self.channel_layer.group_discard(
                        group_name, self.channel_name
                    )
                    logger.debug(f"User {self.user_id} left group: {group_name}")

            # 讓子類進行清理
            await self.cleanup()

        except Exception as e:
            logger.error(f"Error in pre_disconnect: {e}")

    # === 子類需要實作的方法 ===

    async def setup(self):
        """
        子類設定方法，用於定義群組名稱和其他初始化
        子類應該在此方法中設定 self.group_names = [...]
        """
        pass

    async def cleanup(self):
        """
        子類清理方法，可選擇實作
        """
        pass

    async def handle_message(self, data):
        """
        處理客戶端消息，子類可選擇實作
        """
        pass

    # === 輔助方法 ===

    def get_token_from_query(self):
        """從 query string 獲取 JWT token"""
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token_list = query_params.get('token', [])
        return token_list[0] if token_list else None

    @database_sync_to_async
    def authenticate_token(self, token):
        """驗證 JWT token 並返回用戶"""
        try:
            # 驗證 token 格式
            UntypedToken(token)

            # 從 token 獲取用戶 ID
            access_token = AccessToken(token)
            user_id = access_token['user_id']

            # 獲取用戶
            user = User.objects.get(id=user_id, is_active=True)
            return user

        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            logger.error(f"Token authentication failed: {e}")
            return AnonymousUser()

    async def send_error(self, message):
        """發送錯誤消息給客戶端"""
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))

    async def send_success(self, message, data=None):
        """發送成功消息給客戶端"""
        response = {'type': 'success', 'message': message}
        if data:
            response['data'] = data

        await self.send(text_data=json.dumps(response))

    async def heartbeat_loop(self):
        """
        心跳循環：每15秒發送ping，檢查pong回應
        如果2分鐘沒收到pong，主動斷開連接
        """
        try:
            while True:
                await asyncio.sleep(15)  # 每15秒發送一次ping

                # 檢查上次pong時間，如果超過1分鐘則斷線
                # TODO: disconnect in 1 min (currently 30 min for debugging)
                if timezone.now() - self.last_pong > timedelta(minutes=30):
                    logger.warning(f"Heartbeat timeout for user {self.user_id}")
                    await self.close(code=4001)  # 心跳超時
                    break

                # 發送ping
                await self.send(
                    text_data=json.dumps(
                        {'type': 'ping', 'timestamp': timezone.now().isoformat()}
                    )
                )

                logger.debug(f"Sent ping to user {self.user_id}")

        except asyncio.CancelledError:
            logger.debug(
                f"Heartbeat task cancelled for user {getattr(self, 'user_id', 'unknown')}"
            )
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
            await self.close(code=4000)
