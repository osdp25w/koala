#!/usr/bin/env python3
"""
測試新的單一隊列架構
驗證基於message_type的路由機制
透過正常的MQTT流程進行測試
"""

import json
import os
import sys
import time

import django

# 設置 Django 環境
sys.path.append('/usr/src/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')
django.setup()

from koala.mqtt import mqtt_client, publish_bike_telemetry


def test_mqtt_connection():
    """測試MQTT連接"""
    print('🧪 測試MQTT連接...')

    if mqtt_client.connect():
        print('✓ MQTT客戶端連接成功')
        return True
    else:
        print('✗ MQTT客戶端連接失敗')
        return False


def test_telemetry_message():
    """測試遙測消息發布"""
    print('\n🧪 測試遙測消息發布...')

    bike_id = 'test_bike_001'
    telemetry_data = {
        'latitude': 25.0330,
        'longitude': 121.5654,
        'soc': 85,
        'speed': 15.5,
        'temperature': 25,
        'voltage': 12.5,
        'test': True,
    }

    success = publish_bike_telemetry(bike_id, telemetry_data)
    if success:
        print(f"✓ 遙測消息發布成功: bike/{bike_id}/telemetry")
    else:
        print('✗ 遙測消息發布失敗')

    return success


def test_unknown_message():
    """測試未知消息類型"""
    print('\n🧪 測試未知消息類型...')

    # 使用publish_message直接發布到未知主題
    from koala.mqtt import publish_message

    topic = 'bike/test_bike_002/unknown'
    message = json.dumps(
        {'raw_message': 'This is an unknown message type', 'test': True}
    )

    success = publish_message(topic, message)
    if success:
        print(f"✓ 未知消息發布成功: {topic}")
    else:
        print('✗ 未知消息發布失敗')

    return success


def main():
    """主測試函數"""
    print('🚀 開始測試新的單一隊列架構')
    print('=' * 50)

    try:
        # 測試MQTT連接
        if not test_mqtt_connection():
            print('❌ MQTT連接失敗，無法繼續測試')
            return

        # 等待連接穩定
        time.sleep(2)

        # 測試各種消息類型
        test_results = []
        test_results.append(test_telemetry_message())
        test_results.append(test_unknown_message())

        # 等待消息處理
        print('\n⏳ 等待5秒以確保Celery任務被觸發...')
        time.sleep(5)

        # 總結測試結果
        success_count = sum(test_results)
        total_count = len(test_results)

        print(f"\n📊 測試結果: {success_count}/{total_count} 成功")

        if success_count == total_count:
            print('✅ 所有測試通過！')
        else:
            print('⚠️ 部分測試失敗，請檢查日誌')

        print('\n請檢查以下日誌以確認任務執行情況:')
        print('- MQTT客戶端日誌: docker-compose logs koala-mqtt-client')
        print('- Celery Worker日誌: docker-compose logs koala-celery-iot')

    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # 斷開MQTT連接
        if mqtt_client.is_connected:
            mqtt_client.disconnect()
            print('🔌 MQTT連接已斷開')


if __name__ == '__main__':
    main()
