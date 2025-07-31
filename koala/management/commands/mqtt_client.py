import json
import logging
import signal
import sys
import time

from django.core.management.base import BaseCommand

from koala.mqtt import mqtt_client, publish_message, subscribe_topic

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'MQTT 客戶端管理命令 - 連接 RabbitMQ MQTT 插件並處理 IoT 數據'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['start', 'stop', 'status', 'publish', 'subscribe', 'test'],
            default='start',
            help='要執行的動作',
        )
        parser.add_argument(
            '--topic', type=str, help='MQTT 主題 (用於 publish 和 subscribe)'
        )
        parser.add_argument('--message', type=str, help='要發布的消息 (用於 publish)')
        parser.add_argument('--daemon', action='store_true', help='以守護進程模式運行')

    def handle(self, *args, **options):
        action = options['action']

        # 設置日誌級別
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        )

        if action == 'start':
            self.start_mqtt_client(options.get('daemon', False))
        elif action == 'stop':
            self.stop_mqtt_client()
        elif action == 'status':
            self.show_status()
        elif action == 'publish':
            self.publish_message(options['topic'], options['message'])
        elif action == 'subscribe':
            self.subscribe_topic(options['topic'])
        elif action == 'test':
            self.run_test()

    def start_mqtt_client(self, daemon=False):
        """啟動 MQTT 客戶端並開始監聽 IoT 數據"""
        self.stdout.write(self.style.SUCCESS('正在啟動 MQTT 客戶端...'))

        try:
            # 連接到 MQTT broker
            if mqtt_client.connect():
                self.stdout.write(self.style.SUCCESS('MQTT 客戶端連接成功！'))
                self.stdout.write(self.style.SUCCESS('開始監聽 IoT 設備資料並觸發 Celery 任務處理...'))

                # 顯示已訂閱的主題
                self.show_subscribed_topics()

                if daemon:
                    self.stdout.write(self.style.SUCCESS('以守護進程模式運行...'))
                    self.run_daemon()
                else:
                    self.stdout.write(self.style.SUCCESS('MQTT 客戶端已啟動。按 Ctrl+C 停止。'))
                    self.wait_for_signal()
            else:
                self.stdout.write(self.style.ERROR('MQTT 客戶端連接失敗！'))
                sys.exit(1)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'啟動 MQTT 客戶端時發生錯誤: {e}'))
            sys.exit(1)

    def stop_mqtt_client(self):
        """停止 MQTT 客戶端"""
        self.stdout.write(self.style.WARNING('正在停止 MQTT 客戶端...'))
        mqtt_client.disconnect()
        self.stdout.write(self.style.SUCCESS('MQTT 客戶端已停止'))

    def show_status(self):
        """顯示 MQTT 客戶端狀態"""
        status = '已連接' if mqtt_client.is_connected else '未連接'
        self.stdout.write(f'MQTT 客戶端狀態: {status}')

        if mqtt_client.is_connected:
            self.stdout.write(f'重連次數: {mqtt_client.reconnect_count}')
            self.show_subscribed_topics()

    def show_subscribed_topics(self):
        """顯示已訂閱的主題"""
        from django.conf import settings

        if 'AUTO_SUBSCRIBE_TOPICS' in settings.MQTT_CONFIG:
            self.stdout.write('已訂閱的主題:')
            for topic in settings.MQTT_CONFIG['AUTO_SUBSCRIBE_TOPICS']:
                self.stdout.write(f'  - {topic}')

    def publish_message(self, topic, message):
        """發布消息"""
        if not topic or not message:
            self.stdout.write(self.style.ERROR('請提供主題和消息'))
            return

        if publish_message(topic, message):
            self.stdout.write(self.style.SUCCESS(f'消息已發布到 {topic}: {message}'))
        else:
            self.stdout.write(self.style.ERROR('發布消息失敗'))

    def subscribe_topic(self, topic):
        """訂閱主題並顯示接收到的消息"""
        if not topic:
            self.stdout.write(self.style.ERROR('請提供主題名稱'))
            return

        if subscribe_topic(topic):
            self.stdout.write(self.style.SUCCESS(f'已訂閱主題: {topic}'))
            self.stdout.write('等待消息... (按 Ctrl+C 停止)')
            self.wait_for_signal()
        else:
            self.stdout.write(self.style.ERROR('訂閱主題失敗'))

    def run_test(self):
        """運行 MQTT 測試 - 測試發布和接收功能"""
        self.stdout.write(self.style.SUCCESS('開始 MQTT + Celery 整合測試...'))

        # 連接測試
        if not mqtt_client.connect():
            self.stdout.write(self.style.ERROR('連接測試失敗'))
            return

        # 等待連接穩定
        time.sleep(2)

        # 測試腳踏車遙測資料
        test_bike_id = 'test_bike_001'
        test_telemetry = {
            'timestamp': int(time.time()),
            'latitude': 25.0330,
            'longitude': 121.5654,
            'battery_level': 85,
            'speed': 15.5,
            'temperature': 25,
            'voltage': 12.5,
            'test': True,
        }

        telemetry_topic = f'bike/{test_bike_id}/telemetry'
        if publish_message(telemetry_topic, json.dumps(test_telemetry)):
            self.stdout.write(self.style.SUCCESS(f'✓ 腳踏車遙測資料發布成功: {telemetry_topic}'))
        else:
            self.stdout.write(self.style.ERROR('✗ 腳踏車遙測資料發布失敗'))

        # 測試車隊管理資料
        test_fleet = {
            'timestamp': int(time.time()),
            'status': 'available',
            'zone': 'downtown_01',
            'last_maintenance': '2024-01-15',
            'parking_location': {'station_id': 'station_001', 'slot_number': 5},
            'test': True,
        }

        fleet_topic = f'bike/{test_bike_id}/fleet'
        if publish_message(fleet_topic, json.dumps(test_fleet)):
            self.stdout.write(self.style.SUCCESS(f'✓ 車隊管理資料發布成功: {fleet_topic}'))
        else:
            self.stdout.write(self.style.ERROR('✗ 車隊管理資料發布失敗'))

        # 測試運動資料
        test_sport = {
            'timestamp': int(time.time()),
            'user_id': 'test_user_001',
            'session_id': f'session_{test_bike_id}_{int(time.time())}',
            'distance': 5.2,
            'duration': 1800,  # 30 minutes
            'calories_burned': 180,
            'average_speed': 10.4,
            'max_speed': 15.0,
            'test': True,
        }

        sport_topic = f'bike/{test_bike_id}/sport'
        if publish_message(sport_topic, json.dumps(test_sport)):
            self.stdout.write(self.style.SUCCESS(f'✓ 運動資料發布成功: {sport_topic}'))
        else:
            self.stdout.write(self.style.ERROR('✗ 運動資料發布失敗'))

        # 等待消息處理
        self.stdout.write('等待 5 秒以確保 Celery 任務被觸發...')
        time.sleep(5)

        self.stdout.write(self.style.SUCCESS('MQTT + Celery 整合測試完成'))
        self.stdout.write('請檢查 Celery worker 日誌以確認任務是否正常執行')

    def run_daemon(self):
        """以守護進程模式運行"""

        def signal_handler(signum, frame):
            self.stdout.write('\n正在優雅地關閉 MQTT 客戶端...')
            mqtt_client.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while mqtt_client.is_connected:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    def wait_for_signal(self):
        """等待中斷信號"""

        def signal_handler(signum, frame):
            self.stdout.write('\n正在停止 MQTT 客戶端...')
            mqtt_client.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
