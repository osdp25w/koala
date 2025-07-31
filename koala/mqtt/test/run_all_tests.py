#!/usr/bin/env python3
"""
MQTT + Celery 完整測試套件執行器
依序執行所有測試並生成報告
"""

import os
import subprocess
import sys
import time
from datetime import datetime


def run_test_script(script_path, test_name):
    """執行測試腳本"""
    print(f"\n{'='*20} {test_name} {'='*20}")
    print(f"⏰ 開始時間: {datetime.now().strftime('%H:%M:%S')}")

    try:
        # 執行測試腳本
        timeout = 120 if 'iot_device_simulator' in script_path else 60

        # 為IoT設備模擬器添加參數
        cmd = [sys.executable, script_path]
        if 'iot_device_simulator' in script_path:
            cmd.extend(['--bikes', '1', '--duration', '1'])

        # IoT設備模擬器測試使用實時輸出
        if 'iot_device_simulator' in script_path:
            print('🔄 開始IoT設備模擬器測試 (實時輸出)...')
            result = subprocess.run(cmd, text=True, timeout=timeout)
            print('\n📋 IoT設備模擬器測試完成')
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

        print('📋 測試輸出:')
        print(result.stdout)

        if result.stderr:
            print('⚠️ 錯誤輸出:')
            print(result.stderr)

        success = result.returncode == 0
        status = '✅ 通過' if success else '❌ 失敗'
        print(f"📊 結果: {status} (返回碼: {result.returncode})")

        return success

    except subprocess.TimeoutExpired:
        print('⏰ 測試超時!')
        return False
    except Exception as e:
        print(f"💥 執行錯誤: {e}")
        return False


def main():
    """主函數"""
    print('🧪 MQTT + Celery 完整測試套件')
    print('=' * 80)
    print(f"⏰ 測試開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 獲取當前目錄
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 測試腳本列表 - 更新為新的測試檔案
    tests = [
        ('單一隊列架構測試', os.path.join(current_dir, 'test_single_queue_architecture.py')),
    ]

    # 可選的IoT設備模擬器測試（需要較長時間）
    iot_simulator_test = (
        'IoT設備模擬器測試',
        os.path.join(current_dir, 'iot_device_simulator.py'),
    )

    # 檢查是否要執行IoT模擬器測試
    import sys

    if '--include-iot-simulator' in sys.argv:
        tests.append(iot_simulator_test)
        print('📋 包含IoT設備模擬器測試')
    else:
        print('📋 跳過IoT設備模擬器測試 (使用 --include-iot-simulator 參數來包含)')

    results = []

    # 執行所有測試
    for test_name, script_path in tests:
        if os.path.exists(script_path):
            success = run_test_script(script_path, test_name)
            results.append((test_name, success))
        else:
            print(f"⚠️ 測試腳本不存在: {script_path}")
            results.append((test_name, False))

        time.sleep(2)  # 測試間隔

    # 生成測試報告
    print('\n' + '=' * 80)
    print('📊 測試報告')
    print('=' * 80)

    passed = 0
    total = len(results)

    for test_name, success in results:
        status = '✅ 通過' if success else '❌ 失敗'
        print(f"{status} {test_name}")
        if success:
            passed += 1

    print('\n' + '-' * 40)
    print(f"📈 總結: {passed}/{total} 測試通過")
    print(f"⏰ 測試結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 建議和下一步
    print('\n💡 建議和下一步:')

    if passed == total:
        print('🎉 所有測試通過! 您的 MQTT + Celery 整合運行正常')
        print('📋 您可以:')
        print('  1. 運行 IoT 設備模擬器進行更長時間的測試:')
        print(
            f"     python {os.path.join(current_dir, 'iot_device_simulator.py')} --bikes 3 --duration 5"
        )
        print('  2. 檢查 Celery Worker 日誌:')
        print('     docker-compose logs koala-iot-default-worker')
        print('  3. 檢查 MQTT 客戶端日誌:')
        print('     docker-compose logs koala-mqtt-client')
    else:
        print('⚠️ 部分測試失敗，請檢查:')
        print('  1. 服務是否正常運行')
        print('  2. RabbitMQ 連接是否正常')
        print('  3. Celery Worker 是否啟動')
        print('  4. MQTT 客戶端是否連接')

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
