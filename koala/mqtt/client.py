import json
import logging
import threading
import time
import uuid
from typing import Dict, Optional

import paho.mqtt.client as mqtt
from django.conf import settings

logger = logging.getLogger(__name__)


class MQTTClientManager:
    """MQTT 客戶端管理器 - 連接 RabbitMQ MQTT 插件並觸發 Celery 任務"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.client = None
        self.is_connected = False
        self.reconnect_count = 0
        self._setup_client()

    def _setup_client(self):
        """設置 MQTT 客戶端"""
        client_id = f"{settings.MQTT_CONFIG['CLIENT_ID_PREFIX']}_{uuid.uuid4().hex[:8]}"

        self.client = mqtt.Client(
            client_id=client_id, clean_session=settings.MQTT_CONFIG['CLEAN_SESSION']
        )

        # 設置用戶名和密碼
        self.client.username_pw_set(
            settings.MQTT_CONFIG['USERNAME'], settings.MQTT_CONFIG['PASSWORD']
        )

        # 設置回調函數
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe

        logger.info(f"MQTT client initialized with ID: {client_id}")

    def connect(self) -> bool:
        """連接到 MQTT broker"""
        try:
            self.client.connect(
                settings.MQTT_CONFIG['HOST'],
                settings.MQTT_CONFIG['PORT'],
                settings.MQTT_CONFIG['KEEPALIVE'],
            )

            # 啟動網絡循環
            self.client.loop_start()

            # 等待連接建立
            timeout = 10  # 10秒超時
            start_time = time.time()
            while not self.is_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if self.is_connected:
                logger.info('Successfully connected to MQTT broker')
                # 自動訂閱主題
                self._auto_subscribe()
                return True
            else:
                logger.error('Failed to connect to MQTT broker within timeout')
                return False

        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        """斷開 MQTT 連接"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            logger.info('Disconnected from MQTT broker')

    def _auto_subscribe(self):
        """自動訂閱配置的主題"""
        if 'AUTO_SUBSCRIBE_TOPICS' in settings.MQTT_CONFIG:
            for topic in settings.MQTT_CONFIG['AUTO_SUBSCRIBE_TOPICS']:
                result = self.client.subscribe(topic, settings.MQTT_CONFIG['QOS_LEVEL'])
                if result[0] == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Auto-subscribed to topic: {topic}")
                else:
                    logger.error(f"Failed to auto-subscribe to topic: {topic}")

    def subscribe(self, topic: str, qos: int = None) -> bool:
        """訂閱主題"""
        if not self.is_connected:
            logger.warning('MQTT client not connected, attempting to reconnect...')
            if not self.connect():
                logger.error('Failed to reconnect to MQTT broker')
                return False

        try:
            qos = qos if qos is not None else settings.MQTT_CONFIG['QOS_LEVEL']
            result = self.client.subscribe(topic, qos)

            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Subscribed to topic: {topic}")
                return True
            else:
                logger.error(f"Failed to subscribe to {topic}, error code: {result[0]}")
                return False

        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            return False

    def publish(
        self, topic: str, payload: str, qos: int = None, retain: bool = None
    ) -> bool:
        """發布消息到指定主題"""
        if not self.is_connected:
            logger.warning('MQTT client not connected, attempting to reconnect...')
            if not self.connect():
                logger.error('Failed to reconnect to MQTT broker')
                return False

        try:
            qos = qos if qos is not None else settings.MQTT_CONFIG['QOS_LEVEL']
            retain = (
                retain
                if retain is not None
                else settings.MQTT_CONFIG['RETAIN_MESSAGES']
            )

            result = self.client.publish(topic, payload, qos, retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Message published to {topic}")
                return True
            else:
                logger.error(
                    f"Failed to publish message to {topic}, error code: {result.rc}"
                )
                return False

        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """連接回調"""
        if rc == 0:
            self.is_connected = True
            self.reconnect_count = 0
            logger.info('Connected to MQTT broker successfully')
        else:
            self.is_connected = False
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """斷開連接回調"""
        self.is_connected = False
        if rc != 0:
            logger.warning(
                f"Unexpected disconnection from MQTT broker, return code: {rc}"
            )

            # 自動重連邏輯
            if (
                settings.MQTT_CONFIG['AUTO_RECONNECT']
                and self.reconnect_count
                < settings.MQTT_CONFIG['MAX_RECONNECT_ATTEMPTS']
            ):
                self.reconnect_count += 1
                delay = settings.MQTT_CONFIG['RECONNECT_DELAY']
                logger.info(
                    f"Attempting to reconnect in {delay} seconds... (attempt {self.reconnect_count})"
                )

                time.sleep(delay)
                self.connect()
        else:
            logger.info('Disconnected from MQTT broker normally')

    def _on_message(self, client, userdata, msg):
        """消息接收回調 - 觸發 Celery 任務"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')

            logger.info(f"Received MQTT message on {topic}")
            logger.debug(f"Message payload: {payload}")

            # 觸發 Celery 任務處理訊息
            self._trigger_celery_task(topic, payload)

        except Exception as e:
            logger.error(f"Error processing received message: {e}")

    def _trigger_celery_task(self, topic: str, payload: str):
        """觸發對應的 Celery 任務"""
        try:
            # 動態導入避免循環導入
            from koala.mqtt.tasks import process_iot_message

            # 解析payload
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {'raw_message': payload}

            # 從topic推斷message_type
            message_type = self._extract_message_type_from_topic(topic)

            # 構建統一的消息格式
            message_data = {
                'message_type': message_type,
                'bike_id': self._extract_bike_id_from_topic(topic),
                'timestamp': int(time.time()),
                'data': data,
                'metadata': {'source': 'mqtt', 'priority': 'normal'},
            }

            # 異步觸發 Celery 任務
            process_iot_message.delay(topic, message_data)
            logger.debug(
                f"Triggered Celery task for {message_type} message from {topic}"
            )

        except ImportError:
            logger.error(
                'Could not import mqtt_tasks. Make sure koala.mqtt.tasks module exists.'
            )
        except Exception as e:
            logger.error(f"Error triggering Celery task: {e}")

    def _extract_message_type_from_topic(self, topic: str) -> str:
        """從topic中提取message_type"""
        if topic.endswith('/telemetry'):
            return 'telemetry'
        elif topic.endswith('/fleet'):
            return 'fleet'
        elif topic.endswith('/sport'):
            return 'sport'
        else:
            return 'unknown'

    def _extract_bike_id_from_topic(self, topic: str) -> str:
        """從topic中提取bike_id"""
        parts = topic.split('/')
        if len(parts) >= 2:
            return parts[1]
        return 'unknown'

    def _on_publish(self, client, userdata, mid):
        """發布回調"""
        logger.debug(f"Message published successfully, message ID: {mid}")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """訂閱回調"""
        logger.debug(f"Subscription confirmed, message ID: {mid}, QoS: {granted_qos}")


# 全局 MQTT 客戶端實例
mqtt_client = MQTTClientManager()


# 便捷函數
def publish_message(
    topic: str, payload: str, qos: int = None, retain: bool = None
) -> bool:
    """發布 MQTT 消息的便捷函數"""
    return mqtt_client.publish(topic, payload, qos, retain)


def subscribe_topic(topic: str, qos: int = None) -> bool:
    """訂閱 MQTT 主題的便捷函數"""
    return mqtt_client.subscribe(topic, qos)


# 業務相關的發布函數
def publish_bike_telemetry(bike_id: str, telemetry_data: dict) -> bool:
    """發布腳踏車遙測資料"""
    topic = f"bike/{bike_id}/telemetry"
    payload = json.dumps(telemetry_data)
    return publish_message(topic, payload)


def publish_bike_fleet_status(bike_id: str, fleet_data: dict) -> bool:
    """發布車輛管理資料"""
    topic = f"bike/{bike_id}/fleet"
    payload = json.dumps(fleet_data)
    return publish_message(topic, payload)


def publish_bike_sport_metrics(bike_id: str, sport_data: dict) -> bool:
    """發布運動資料"""
    topic = f"bike/{bike_id}/sport"
    payload = json.dumps(sport_data)
    return publish_message(topic, payload)
