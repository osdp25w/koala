#!/usr/bin/env python
"""
真實時間自行車租賃模擬腳本
- IoT訊息每10秒發送一次（真實時間）
- 不使用時間patch，讓所有任務自然觸發
- Member循環測試每台可用的腳踏車
- 持續運行直到 Ctrl+C 停止
- --debug: 只使用3分鐘短路線進行測試
"""

import argparse
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta

# 設定Django環境
sys.path.append('/usr/src/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')

import django

django.setup()

from django.utils import timezone

from account.models import Member
from bike.models import BikeInfo
from simulator.routes import TEST_ROUTES
from simulator.services import BikeRentalSimulator, OSRMRouteService

# 配置常數
IOT_INTERVAL_SECONDS = 10  # IoT訊息發送間隔（秒）
SIMULATION_PAUSE_SECONDS = 30  # 每次模擬完成後的等待時間（秒）
RETRY_WAIT_SECONDS = 30  # 發生錯誤或無可用自行車時的等待時間（秒）


class RealtimeSimulationRunner:
    """真實時間模擬運行器"""

    def __init__(self, debug_mode=False):
        self.running = True
        self.current_member_index = 0
        self.simulation_count = 0
        self.debug_mode = debug_mode

        # 設定信號處理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """處理停止信號"""
        print(f"\n\n收到停止信號 {signum}，正在優雅地停止模擬...")
        self.running = False

    def get_available_bikes(self):
        """獲取可用的自行車"""
        bikes = BikeInfo.objects.filter(bike_id__contains='SIMULATOR').select_related(
            'realtime_status'
        )
        available_bikes = [
            bike
            for bike in bikes
            if hasattr(bike, 'realtime_status')
            and bike.realtime_status.status == bike.realtime_status.StatusOptions.IDLE
            and bike.realtime_status.get_is_rentable()
        ]
        return available_bikes

    def get_members(self):
        """獲取測試會員"""
        return list(Member.objects.filter(username__startswith='SIMULATOR-member'))

    def simulate_realtime_iot_messages(self, bike: BikeInfo, route_points: list):
        """真實時間發送IoT訊息（每10秒一次）"""
        from telemetry.services import IoTRawProcessService

        print(
            f"📡 開始真實時間IoT模擬，總共 {len(route_points)} 個點，預計 {len(route_points) * IOT_INTERVAL_SECONDS} 秒"
        )

        for i, point in enumerate(route_points):
            if not self.running:
                print('⏹️ 模擬被中斷，停止發送IoT訊息')
                break

            print(
                f"📍 發送第 {i+1}/{len(route_points)} 個IoT訊息: ({point['lat']:.6f}, {point['lng']:.6f})"
            )

            # 發送IoT訊息 - 使用IoT協議格式
            current_time = timezone.localtime().strftime('%Y%m%d%H%M%S')

            # 1%機率觸發錯誤
            should_trigger_error = random.random() < 0.01
            error_type = None

            if should_trigger_error:
                # 隨機選擇錯誤類型
                error_types = ['low_battery', 'overheating', 'gps_poor', 'signal_weak']
                error_type = random.choice(error_types)
                print(f"⚠️  觸發 {error_type} 錯誤")

            msg_data = {
                # 必需字段
                'BI': bike.bike_id,  # Bike ID
                # 時間資訊
                'GT': current_time,  # GPS時間
                'RT': current_time,  # RTC時間
                'ST': current_time,  # 發送時間
                # GPS位置資訊
                'LA': int(point['lat'] * 1000000),  # 緯度
                'LG': int(point['lng'] * 1000000),  # 經度
                'HD': random.randint(0, 360),  # 方向
                'VS': random.randint(8, 25),  # 車速 km/h
                'AT': random.randint(0, 100),  # 海拔
                'HP': random.randint(10, 50),  # GPS HDOP * 10
                'VP': random.randint(10, 50),  # GPS VDOP * 10
                'SA': random.randint(1, 3)
                if error_type == 'gps_poor'
                else random.randint(4, 12),  # GPS信號差
                # 電池與動力資訊
                'MV': random.randint(480, 540),  # 電池電壓 * 10 (48-54V)
                'SO': random.randint(5, 9)
                if error_type == 'low_battery'
                else random.randint(30, 100),  # 低電量錯誤
                'EO': random.randint(0, 50000),  # 里程計 (米)
                'AL': random.randint(0, 4),  # 助力等級
                'PT': random.randint(0, 5000),  # 踏板扭矩 * 100
                'CT': random.randint(700, 900)
                if error_type == 'overheating'
                else random.randint(200, 600),  # 控制器過熱
                'CA': random.randint(0, 4000),  # 踏板轉速 * 40
                'TP1': random.randint(700, 900)
                if error_type == 'overheating'
                else random.randint(150, 450),  # 電池過熱
                'TP2': random.randint(700, 900)
                if error_type == 'overheating'
                else random.randint(150, 450),  # 電池過熱
                # 系統狀態
                'IN': 1,  # ACC狀態 (開啟)
                'OP': 0,  # 輸出狀態
                'AI1': random.randint(11000, 13000),  # 類比輸入 * 1000
                'BV': random.randint(110, 130),  # 備用電池電壓 * 10
                'GQ': random.randint(1, 3)
                if error_type == 'signal_weak'
                else random.randint(10, 31),  # 信號弱
                'OD': random.randint(0, 10000),  # 總里程 * 10
                'DD': '',  # 會員ID (可為空)
                # 報告資訊
                'RD': 2,  # 正常更新
                'MS': '',  # 訊息 (無錯誤時為空)
            }

            try:
                result = IoTRawProcessService.process_telemetry_message(
                    device_id=bike.telemetry_device.IMEI,
                    sequence_id=i + 1,
                    msg_data=msg_data,
                )
                print(f"✅ IoT訊息發送成功: {result}")
            except Exception as e:
                import traceback

                print(f"❌ IoT訊息發送失敗: {e}")
                print(f"完整錯誤: {traceback.format_exc()}")
                print(f"發送的數據: {msg_data}")
                break  # 停止發送，避免重複錯誤

            # 等待指定秒數（除非是最後一個點）
            if i < len(route_points) - 1:
                print(f"⏱️ 等待{IOT_INTERVAL_SECONDS}秒...")
                time.sleep(IOT_INTERVAL_SECONDS)

        print('📡 IoT訊息發送完成')

    def simulate_one_rental(self, bike: BikeInfo, member: Member, route_config: dict):
        """模擬一次真實時間租賃"""
        from rest_framework.test import APIClient

        print(f"\n🚴 開始租賃: {member.username} 租借 {bike.bike_id}")
        print(f"📍 路線: {route_config['name']}")

        try:
            # 1. 調用租車API
            client = APIClient()
            client.force_authenticate(user=member.user)

            response = client.post(
                '/api/rental/member/rentals/',
                data={'bike_id': bike.bike_id},
                format='json',
            )

            response_data = response.json()

            if response_data.get('code') != 2000:
                print(f"❌ 租車失敗: {response_data}")
                return False

            rental_id = response_data['data']['id']
            print(f"✅ 租車成功，租賃ID: {rental_id}")

            # 2. 獲取路線座標
            route_points = OSRMRouteService.get_route_with_timing(route_config)
            if not route_points:
                print('❌ 無法獲取路線座標，但仍嘗試還車')
            else:
                # 3. 真實時間發送IoT訊息
                try:
                    self.simulate_realtime_iot_messages(bike, route_points)
                except Exception as e:
                    print(f"❌ IoT訊息發送過程發生異常: {e}")

            # 4. 調用還車API（無論IoT是否成功都要還車）
            print(f"🔄 準備還車...")
            response = client.patch(
                f'/api/rental/member/rentals/{rental_id}/',
                data={'action': 'return'},
                format='json',
            )

            response_data = response.json()

            if response_data.get('code') == 2000:
                print(f"✅ 還車成功")
                return True
            else:
                print(f"❌ 還車失敗: {response_data}")
                return False

        except Exception as e:
            print(f"❌ 租賃過程發生異常: {e}")
            return False

    def run_continuous_simulation(self):
        """持續運行模擬"""
        print('=' * 60)
        print('🚴‍♂️ 開始真實時間自行車租賃模擬')
        print(f"📡 IoT訊息每{IOT_INTERVAL_SECONDS}秒發送一次")
        print('🔄 Member循環測試每台可用腳踏車')
        if self.debug_mode:
            print('🐛 DEBUG模式: 只使用3分鐘短路線測試')
        print('⏹️ 按 Ctrl+C 停止模擬')
        print('=' * 60)

        members = self.get_members()
        if not members:
            print('❌ 找不到測試會員，請先建立測試數據')
            return

        print(f"👥 載入 {len(members)} 個測試會員")
        print(f"🗺️ 載入 {len(TEST_ROUTES)} 條測試路線")

        while self.running:
            try:
                # 獲取當前可用的自行車
                available_bikes = self.get_available_bikes()

                if not available_bikes:
                    print(f"⏳ 目前沒有可用的自行車，等待{RETRY_WAIT_SECONDS}秒後重試...")
                    time.sleep(RETRY_WAIT_SECONDS)
                    continue

                # 循環使用會員
                current_member = members[self.current_member_index]
                self.current_member_index = (self.current_member_index + 1) % len(
                    members
                )

                # 選擇一台可用的自行車
                bike = random.choice(available_bikes)

                # 選擇路線 - debug模式只用短路線
                if self.debug_mode:
                    route_config = TEST_ROUTES[0]  # 使用第一條路線（3分鐘短路線）
                else:
                    route_config = random.choice(TEST_ROUTES)

                self.simulation_count += 1
                print(f"\n🎯 第 {self.simulation_count} 次模擬")

                # 執行模擬
                success = self.simulate_one_rental(bike, current_member, route_config)

                if success:
                    print(f"✅ 第 {self.simulation_count} 次模擬完成")
                else:
                    print(f"❌ 第 {self.simulation_count} 次模擬失敗")

                if self.running:
                    print(f"⏱️ 等待{SIMULATION_PAUSE_SECONDS}秒後開始下一次模擬...")
                    time.sleep(SIMULATION_PAUSE_SECONDS)

            except KeyboardInterrupt:
                print('\n👋 收到中斷信號，正在停止模擬...')
                break
            except Exception as e:
                print(f"❌ 模擬過程發生異常: {e}")
                if self.running:
                    print(f"⏱️ 等待{RETRY_WAIT_SECONDS}秒後重試...")
                    time.sleep(RETRY_WAIT_SECONDS)

        print(f"\n🏁 模擬結束，總共完成 {self.simulation_count} 次租賃模擬")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='真實時間自行車租賃模擬腳本')
    parser.add_argument('--debug', action='store_true', help='DEBUG模式：只使用3分鐘短路線測試')

    args = parser.parse_args()

    runner = RealtimeSimulationRunner(debug_mode=args.debug)
    runner.run_continuous_simulation()


if __name__ == '__main__':
    main()
