#!/usr/bin/env python3
"""
IoT 設備模擬器
模擬真實的腳踏車 IoT 設備發送各種資料
"""

import json
import os
import random
import sys
import threading
import time
from datetime import datetime, timedelta

# Django 設定
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')

import django

django.setup()

from koala.mqtt import mqtt_client, publish_bike_telemetry


class BikeSimulator:
    """腳踏車模擬器 - 模擬真實 IoT 設備資料格式"""

    def __init__(self, bike_info):
        # 使用真實的 BikeInfo 物件
        self.bike_info = bike_info
        self.bike_id = bike_info.bike_id
        self.device_imei = bike_info.telemetry_device.IMEI
        self.is_running = False
        self.is_rented = False
        self.current_member = None  # Member 物件
        self.current_user = None  # member.username
        self.session_start_time = None
        self.sequence_number = 0

        # 初始位置 (台北車站附近) - 轉換為 IoT 格式 (* 10^6)
        base_lat = 25.0330 + random.uniform(-0.01, 0.01)
        base_lng = 121.5654 + random.uniform(-0.01, 0.01)
        self.lat = int(base_lat * 1000000)  # 緯度 * 10^6
        self.lng = int(base_lng * 1000000)  # 經度 * 10^6

        # 腳踏車狀態
        self.battery_level = random.randint(60, 100)  # SOC 百分比
        self.battery_voltage = random.randint(115, 130)  # 電池電壓 * 10 (11.5V-13.0V)
        self.speed = 0  # 當前速度 km/hr
        self.heading_direction = random.randint(0, 365)  # 方向角度
        self.altitude = random.randint(5, 50)  # 海拔高度

        # GPS 相關
        self.gps_hdop = random.randint(10, 30)  # HDOP * 10
        self.gps_vdop = random.randint(10, 30)  # VDOP * 10
        self.satellites_count = random.randint(6, 12)  # 衛星數量

        # 車輛里程和動力
        self.bike_odometer = random.randint(1000, 50000)  # 車輛里程 公尺
        self.total_odometer = random.randint(100000, 500000)  # 總里程 * 10
        self.assist_level = random.randint(0, 4)  # 助力等級
        self.pedal_torque = 0  # 踏板扭力 * 100
        self.pedal_cadence = 0  # 踏板轉速 * 40

        # 溫度 (可能為 NULL)
        self.controller_temp = random.randint(25, 60) if random.random() > 0.1 else None
        self.battery_temp1 = random.randint(20, 40) if random.random() > 0.1 else None
        self.battery_temp2 = random.randint(20, 40) if random.random() > 0.1 else None

        # 系統狀態
        self.acc_status = False  # ACC 狀態
        self.output_status = 0  # 輸出狀態
        self.analog_input = random.randint(10000, 15000)  # 類比輸入 * 1000
        self.backup_battery = random.randint(115, 130)  # 備用電池 * 10
        self.rssi = random.randint(15, 31)  # 訊號強度

        # 運動統計
        self.session_distance = 0
        self.session_calories = 0

    def start_rental(self, member):
        """開始租借 - 使用真實 Member 物件"""
        self.is_rented = True
        self.current_member = member
        self.current_user = str(member.id)  # DD 欄位使用 member_id
        self.session_start_time = datetime.now()
        self.session_distance = 0
        self.session_calories = 0
        self.acc_status = True  # ACC 開啟
        print(f"🚴 會員 {member.username} ({member.full_name}) 開始租借腳踏車 {self.bike_id}")

    def end_rental(self):
        """結束租借"""
        if self.is_rented:
            print(f"🏁 會員 {self.current_user} 結束租借腳踏車 {self.bike_id}")
            self.is_rented = False
            self.current_member = None
            self.current_user = None
            self.session_start_time = None
            self.speed = 0
            self.acc_status = False  # ACC 關閉

    def move(self):
        """模擬移動和狀態更新"""
        if self.is_rented and self.acc_status:
            # 隨機移動 (IoT 格式)
            lat_offset = random.randint(-100, 100)  # ±0.0001 度
            lng_offset = random.randint(-100, 100)
            self.lat += lat_offset
            self.lng += lng_offset

            # 隨機速度和方向
            self.speed = random.randint(5, 25)  # km/hr
            self.heading_direction = (
                self.heading_direction + random.randint(-10, 10)
            ) % 365

            # 動力相關數據
            self.pedal_torque = random.randint(500, 2000)  # 踏板扭力 * 100
            self.pedal_cadence = random.randint(1200, 3200)  # 踏板轉速 * 40

            # 助力等級隨機調整
            if random.random() < 0.1:
                self.assist_level = random.randint(0, 4)

            # 更新里程
            distance_increment = self.speed * 5 / 3600 * 1000  # 5秒內的距離(公尺)
            self.bike_odometer += int(distance_increment)
            self.total_odometer += int(distance_increment * 10)  # 總里程格式 * 10

            # 電池消耗
            if random.random() < 0.02:  # 2% 機率
                self.battery_level = max(0, self.battery_level - 1)
                self.battery_voltage = max(100, self.battery_voltage - 1)
        else:
            self.speed = 0
            self.pedal_torque = 0
            self.pedal_cadence = 0

        # 隨機更新溫度
        if random.random() < 0.1:
            if self.controller_temp is not None:
                self.controller_temp += random.randint(-2, 3)
                self.controller_temp = max(20, min(80, self.controller_temp))
            if self.battery_temp1 is not None:
                self.battery_temp1 += random.randint(-1, 2)
                self.battery_temp1 = max(15, min(50, self.battery_temp1))
            if self.battery_temp2 is not None:
                self.battery_temp2 += random.randint(-1, 2)
                self.battery_temp2 = max(15, min(50, self.battery_temp2))

        # 更新其他狀態
        self.rssi = max(5, min(31, self.rssi + random.randint(-2, 2)))
        self.satellites_count = max(
            4, min(12, self.satellites_count + random.randint(-1, 1))
        )

    def send_telemetry(self):
        """發送遙測資料 - 按 IoT 協議格式"""
        self.sequence_number += 1

        # 生成時間戳 (YYYYMMDDhhmmss 格式)
        now = datetime.now()
        time_str = now.strftime('%Y%m%d%H%M%S')

        # IoT 設備標準格式
        iot_data = {
            'ID': self.device_imei,
            'SQ': self.sequence_number,
            'MSG': {
                # 時間資訊
                'GT': time_str,  # GPS時間
                'RT': time_str,  # RTC時間
                'ST': time_str,  # 發送時間
                # GPS 位置資訊
                'LG': self.lng,  # 經度 * 10^6
                'LA': self.lat,  # 緯度 * 10^6
                'HD': self.heading_direction,  # 方向 0-365度
                'VS': self.speed,  # 車速 km/hr
                'AT': self.altitude,  # 海拔 公尺
                'HP': self.gps_hdop,  # GPS HDOP * 10
                'VP': self.gps_vdop,  # GPS VDOP * 10
                'SA': self.satellites_count,  # 衛星數量
                # 電池與動力資訊
                'MV': self.battery_voltage,  # 電池電壓 * 10
                'SO': self.battery_level,  # 電量百分比
                'EO': self.bike_odometer,  # 車輛里程 公尺
                'AL': self.assist_level,  # 助力等級 0-4
                'PT': self.pedal_torque,  # 踏板扭力 * 100
                'CT': self.controller_temp,  # 控制器溫度 (可為NULL)
                'CA': self.pedal_cadence,  # 踏板轉速 * 40
                'TP1': self.battery_temp1,  # 電池溫度1 (可為NULL)
                'TP2': self.battery_temp2,  # 電池溫度2 (可為NULL)
                # 系統狀態資訊
                'IN': 1 if self.acc_status else 0,  # ACC狀態
                'OP': self.output_status,  # 輸出狀態
                'AI1': self.analog_input,  # 類比輸入 * 1000
                'BV': self.backup_battery,  # 備用電池 * 10
                'GQ': self.rssi,  # 訊號強度 0-31
                'OD': self.total_odometer,  # 總里程 * 10
                'DD': self.current_user or '',  # 會員ID
                'BI': self.bike_id,  # 車輛ID (必要欄位)
                # 報告資訊
                'RD': 1,  # 報告類型 (一般遙測)
                'MS': '',  # 訊息內容
            },
        }

        success = publish_bike_telemetry(self.bike_id, iot_data)
        if success:
            print(
                f"📡 {self.bike_id} (IMEI:{self.device_imei}) 遙測資料已發送 (電池: {self.battery_level}%, 速度: {self.speed}km/h, SQ: {self.sequence_number})"
            )
        return success

    def send_error_report(self, error_code=None, error_message=''):
        """發送錯誤報告 - 使用 IoT 格式"""
        self.sequence_number += 1

        # 生成時間戳
        now = datetime.now()
        time_str = now.strftime('%Y%m%d%H%M%S')

        # 隨機錯誤代碼或使用指定的
        if error_code is None:
            error_codes = [2001, 2002, 1001, 1002]  # 常見錯誤代碼
            error_code = random.choice(error_codes)

        iot_data = {
            'ID': self.device_imei,
            'SQ': self.sequence_number,
            'MSG': {
                'GT': time_str,
                'RT': time_str,
                'ST': time_str,
                'LG': self.lng,
                'LA': self.lat,
                'HD': self.heading_direction,
                'VS': self.speed,
                'AT': self.altitude,
                'HP': self.gps_hdop,
                'VP': self.gps_vdop,
                'SA': self.satellites_count,
                'MV': self.battery_voltage,
                'SO': self.battery_level,
                'EO': self.bike_odometer,
                'AL': self.assist_level,
                'PT': self.pedal_torque,
                'CT': self.controller_temp,
                'CA': self.pedal_cadence,
                'TP1': self.battery_temp1,
                'TP2': self.battery_temp2,
                'IN': 1 if self.acc_status else 0,
                'OP': self.output_status,
                'AI1': self.analog_input,
                'BV': self.backup_battery,
                'GQ': self.rssi,
                'OD': self.total_odometer,
                'DD': self.current_user or '',
                'BI': self.bike_id,  # 車輛ID (必要欄位)
                'RD': error_code,  # 錯誤報告類型
                'MS': error_message,  # 錯誤訊息
            },
        }

        success = publish_bike_telemetry(self.bike_id, iot_data)
        if success:
            print(
                f"⚠️ {self.bike_id} 錯誤報告已發送 (錯誤代碼: {error_code}, 訊息: {error_message})"
            )
        return success

    def simulate_battery_warning(self):
        """模擬電池低電量警告"""
        if self.battery_level < 20:
            return self.send_error_report(1001, f"Low battery: {self.battery_level}%")
        return False

    def simulate_temperature_warning(self):
        """模擬溫度異常警告"""
        if self.controller_temp and self.controller_temp > 65:
            return self.send_error_report(
                2001, f"High controller temp: {self.controller_temp}°C"
            )
        if self.battery_temp1 and self.battery_temp1 > 45:
            return self.send_error_report(
                2002, f"High battery temp1: {self.battery_temp1}°C"
            )
        return False

    def simulate_error_scenarios(self):
        """模擬各種錯誤場景以測試錯誤檢測系統"""
        error_triggered = False

        # 先隨機恢復一些可能的異常狀態到正常範圍
        if random.random() < 0.3:  # 30% 機率恢復正常
            self.satellites_count = random.randint(4, 12)  # 正常GPS衛星數
            self.rssi = random.randint(10, 31)  # 正常RSSI
            self.battery_temp1 = (
                random.randint(20, 45)
                if self.battery_temp1 != 2000
                else self.battery_temp1
            )
            self.battery_temp2 = (
                random.randint(20, 45)
                if self.battery_temp2 != 2000
                else self.battery_temp2
            )
            self.controller_temp = (
                random.randint(25, 50)
                if self.controller_temp != 2000
                else self.controller_temp
            )
            if self.battery_level < 50:  # 如果電量太低，有機會恢復
                self.battery_level = random.randint(50, 100)

        # 1. GPS訊號異常 (SA < 4) - 觸發不同嚴重程度
        if random.random() < 0.08:  # 8% 機率
            severity = random.choice(['mild', 'severe'])
            if severity == 'mild':
                self.satellites_count = 3  # 剛好低於閾值
                print(f"🛰️ {self.bike_id} 模擬GPS輕微異常 (衛星數: {self.satellites_count})")
            else:
                self.satellites_count = random.randint(0, 2)  # 嚴重異常
                print(f"🛰️ {self.bike_id} 模擬GPS嚴重異常 (衛星數: {self.satellites_count})")
            error_triggered = True

        # 2. 電池溫度警告/嚴重 (TP1/TP2 >= 55/60) - 不同等級異常
        if random.random() < 0.06:  # 6% 機率
            temp_sensor = random.choice(['TP1', 'TP2', 'both'])
            severity = random.choice(['warning', 'critical'])

            if severity == 'warning':
                temp_value = random.randint(55, 59)  # 警告等級
                level_text = '警告'
            else:
                temp_value = random.randint(60, 75)  # 嚴重等級
                level_text = '嚴重'

            if temp_sensor in ['TP1', 'both']:
                self.battery_temp1 = temp_value
                print(
                    f"🌡️ {self.bike_id} 模擬電池溫度{level_text} (TP1: {self.battery_temp1}°C)"
                )
            if temp_sensor in ['TP2', 'both']:
                self.battery_temp2 = temp_value
                print(
                    f"🌡️ {self.bike_id} 模擬電池溫度{level_text} (TP2: {self.battery_temp2}°C)"
                )
            error_triggered = True

        # 3. 電池電量警告/嚴重 (SO < 20/10) - 精確觸發閾值
        if random.random() < 0.07:  # 7% 機率
            severity = random.choice(['warning', 'critical', 'edge'])

            if severity == 'warning':
                self.battery_level = random.randint(10, 19)  # 警告範圍
                print(f"🔋 {self.bike_id} 模擬電池電量警告 ({self.battery_level}%)")
            elif severity == 'critical':
                self.battery_level = random.randint(1, 9)  # 嚴重範圍
                print(f"⚡ {self.bike_id} 模擬電池電量嚴重 ({self.battery_level}%)")
            else:  # edge cases
                self.battery_level = random.choice([20, 10])  # 邊界值測試
                print(f"🔋 {self.bike_id} 模擬電池電量邊界測試 ({self.battery_level}%)")
            error_triggered = True

        # 4. RSSI訊號異常 (GQ < 4) - 不同強度的訊號問題
        if random.random() < 0.08:  # 8% 機率
            signal_quality = random.choice(['poor', 'very_poor', 'no_signal'])

            if signal_quality == 'poor':
                self.rssi = 3  # 剛好低於閾值
                print(f"📶 {self.bike_id} 模擬RSSI訊號較差 (RSSI: {self.rssi})")
            elif signal_quality == 'very_poor':
                self.rssi = random.randint(1, 2)
                print(f"📶 {self.bike_id} 模擬RSSI訊號很差 (RSSI: {self.rssi})")
            else:
                self.rssi = 0  # 無訊號
                print(f"📶 {self.bike_id} 模擬RSSI無訊號 (RSSI: {self.rssi})")
            error_triggered = True

        # 5. 感測器異常 (CT/TP1/TP2 == 2000) - 感測器故障
        if random.random() < 0.03:  # 3% 機率
            # 可能同時多個感測器故障
            sensors_to_fail = random.choice(
                [
                    ['CT'],
                    ['TP1'],
                    ['TP2'],
                    ['CT', 'TP1'],
                    ['TP1', 'TP2'],
                    ['CT', 'TP1', 'TP2'],  # 多重故障
                ]
            )

            for sensor in sensors_to_fail:
                if sensor == 'CT':
                    self.controller_temp = 2000
                    print(f"🔧 {self.bike_id} 模擬控制器感測器異常 (CT: 2000)")
                elif sensor == 'TP1':
                    self.battery_temp1 = 2000
                    print(f"🔧 {self.bike_id} 模擬電池溫度1感測器異常 (TP1: 2000)")
                elif sensor == 'TP2':
                    self.battery_temp2 = 2000
                    print(f"🔧 {self.bike_id} 模擬電池溫度2感測器異常 (TP2: 2000)")
            error_triggered = True

        # 6. 遙測設備異常 (RD = 101 或 22)
        if random.random() < 0.01:  # 1% 機率
            error_code = random.choice([101, 22])
            if error_code == 101:
                self.send_error_report(101, '設備錯誤條件')
                print(f"🚨 {self.bike_id} 模擬遙測設備錯誤條件 (RD: 101)")
            else:
                error_msg = random.choice(['感測器校正失敗', '記憶體錯誤', '通訊模組異常', '電源管理錯誤'])
                self.send_error_report(22, error_msg)
                print(f"🚨 {self.bike_id} 模擬遙測設備錯誤代碼 (RD: 22, MSG: {error_msg})")
            error_triggered = True

        return error_triggered

    def simulate_location_anomaly(self):
        """模擬位置異常 - 短時間內大幅位移"""
        if random.random() < 0.005:  # 0.5% 機率
            # 模擬瞬間大幅移動
            jump_distance = random.choice([1500, 3000, 8000])  # 1.5km, 3km, 8km

            # 隨機方向跳躍
            angle = random.uniform(0, 2 * 3.14159)
            lat_jump = jump_distance * 0.000009 * 1000000  # 約 0.000009度/公尺 * 10^6
            lng_jump = jump_distance * 0.000011 * 1000000  # 約 0.000011度/公尺 * 10^6

            import math

            self.lat += int(lat_jump * math.cos(angle))
            self.lng += int(lng_jump * math.sin(angle))

            print(f"🚁 {self.bike_id} 模擬位置異常跳躍 (距離: ~{jump_distance}m)")
            return True
        return False


class IoTDeviceSimulator:
    """IoT 設備模擬器主類 - 使用真實 DB 資料"""

    def __init__(self, num_bikes=None, test_errors=False, error_only=False):
        self.bikes = []
        self.members = []
        self.is_running = False
        self.test_errors = test_errors
        self.error_only = error_only

        # 初始化MQTT客戶端連接
        print('🔌 初始化MQTT客戶端連接...')
        if mqtt_client.connect():
            print('✅ MQTT客戶端連接成功')
        else:
            print('❌ MQTT客戶端連接失敗')

        # 載入真實的會員資料
        self._load_members()

        # 載入真實的腳踏車資料
        self._load_bikes(num_bikes)

        print(f"🚲 載入 {len(self.bikes)} 輛真實腳踏車")
        print(f"👥 載入 {len(self.members)} 位會員")

        # 測試模式提示
        if self.error_only:
            print('🧪 錯誤測試模式: 僅發送錯誤場景數據')
        elif self.test_errors:
            print('⚠️ 錯誤測試模式: 增加錯誤場景機率')

    def _load_members(self):
        """載入真實的會員資料"""
        try:
            from account.models import Member

            self.members = list(Member.objects.filter(is_active=True)[:20])  # 最多 20 位會員
            if not self.members:
                print('⚠️ 警告: 沒有找到會員資料，請先執行 account 腳本創建會員')
        except Exception as e:
            print(f"❌ 載入會員資料錯誤: {e}")
            self.members = []

    def _load_bikes(self, num_bikes=None):
        """載入真實的腳踏車資料"""
        try:
            from bike.models import BikeInfo

            available_bikes = list(BikeInfo.objects.filter(is_active=True))

            if not available_bikes:
                print('⚠️ 警告: 沒有找到腳踏車資料，請先執行 bike 腳本創建腳踏車')
                return

            # 如果指定數量，則隨機選擇
            if num_bikes and num_bikes < len(available_bikes):
                available_bikes = random.sample(available_bikes, num_bikes)

            # 創建 BikeSimulator 物件
            for bike_info in available_bikes:
                try:
                    simulator = BikeSimulator(bike_info)
                    self.bikes.append(simulator)
                except Exception as e:
                    print(f"⚠️ 創建腳踏車模擬器失敗 {bike_info.bike_id}: {e}")

        except Exception as e:
            print(f"❌ 載入腳踏車資料錯誤: {e}")
            self.bikes = []

    def run_error_test_only(self, duration_minutes=5):
        """僅運行錯誤測試場景"""
        print(f"🧪 開始錯誤場景測試 (持續 {duration_minutes} 分鐘)")

        self.is_running = True
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        cycle_count = 0

        while self.is_running and time.time() < end_time:
            cycle_count += 1

            for bike in self.bikes:
                # 強制觸發各種錯誤場景
                if cycle_count % 3 == 1:  # GPS異常
                    bike.satellites_count = random.randint(1, 3)

                if cycle_count % 3 == 2:  # 電池問題
                    if random.random() < 0.5:
                        bike.battery_level = random.randint(5, 15)
                    else:
                        bike.battery_temp1 = random.randint(55, 65)

                if cycle_count % 3 == 0:  # 其他錯誤
                    error_type = random.choice(['rssi', 'sensor', 'device'])
                    if error_type == 'rssi':
                        bike.rssi = random.randint(0, 3)
                    elif error_type == 'sensor':
                        bike.controller_temp = 2000
                    else:
                        bike.send_error_report(random.choice([101, 22]), '測試錯誤')

                # 位置跳躍測試
                if cycle_count % 5 == 0:
                    bike.simulate_location_anomaly()

                # 發送數據
                bike.send_telemetry()

            print(f"🧪 錯誤測試循環 {cycle_count} 完成 (剩餘: {int(end_time - time.time())}秒)")
            time.sleep(2)  # 錯誤測試模式稍慢

        print('✅ 錯誤場景測試完成')

    def start_simulation(self, duration_minutes=10):
        """開始模擬"""
        print(f"🚀 開始 IoT 設備模擬 (持續 {duration_minutes} 分鐘)")

        self.is_running = True
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        # 隨機讓一些腳踏車開始租借 (使用真實會員)
        if self.members and self.bikes:
            num_to_rent = max(1, min(len(self.bikes) // 2, len(self.members)))
            selected_bikes = random.sample(
                self.bikes, min(num_to_rent, len(self.bikes))
            )
            selected_members = random.sample(self.members, len(selected_bikes))

            for bike, member in zip(selected_bikes, selected_members):
                bike.start_rental(member)

        cycle_count = 0

        while self.is_running and time.time() < end_time:
            cycle_count += 1

            for bike in self.bikes:
                # 移動腳踏車和更新狀態
                bike.move()

                # 模擬位置異常 (在move之後，telemetry之前)
                bike.simulate_location_anomaly()

                # 發送遙測資料 (每次循環) - 主要資料傳輸
                bike.send_telemetry()

                # 檢查警告狀態 (每5次循環)
                if cycle_count % 5 == 0:
                    bike.simulate_battery_warning()
                    bike.simulate_temperature_warning()

                # 新的錯誤場景模擬 (根據測試模式調整頻率)
                error_check_interval = 2 if self.test_errors else 10
                if cycle_count % error_check_interval == 0:
                    bike.simulate_error_scenarios()

                # 隨機錯誤事件 (低機率)
                if random.random() < 0.001:  # 0.1% 機率
                    error_messages = ['系統自檢完成', '車輛異常振動', '網路訊號不穩', '齎盤需調整']
                    bike.send_error_report(
                        random.randint(3001, 3010), random.choice(error_messages)
                    )

                # 隨機租借事件 (使用真實會員資料)
                if random.random() < 0.003:  # 0.3% 機率
                    if bike.is_rented:
                        bike.end_rental()
                    else:
                        if self.members:  # 確保有會員資料
                            member = random.choice(self.members)
                            bike.start_rental(member)

            print(
                f"⏰ 模擬循環 {cycle_count} 完成 (剩餘時間: {int(end_time - time.time())}秒, 活躍設備: {sum(1 for b in self.bikes if b.is_rented)}/{len(self.bikes)})"
            )
            time.sleep(1)  # 每1秒一個循環，模擬高頻率傳輸

        # 結束所有租借
        for bike in self.bikes:
            if bike.is_rented:
                bike.end_rental()

        print(f"📋 模擬結果統計:")
        print(f"  - 總傳輸訊息數: {sum(bike.sequence_number for bike in self.bikes)}")
        print(
            f"  - 平均每輛訊息: {sum(bike.sequence_number for bike in self.bikes) / len(self.bikes):.1f}"
            if self.bikes
            else '  - 沒有車輛資料'
        )
        print(f"  - 使用的真實車輛: {[bike.bike_id for bike in self.bikes]}")
        print(
            f"  - 最終電池狀態: {[f'{bike.bike_id}:{bike.battery_level}%' for bike in self.bikes]}"
        )

        # 斷開MQTT連接
        mqtt_client.disconnect()
        print('🔌 MQTT客戶端已斷開連接')
        print('🏁 IoT 設備模擬結束')

    def stop_simulation(self):
        """停止模擬"""
        print('⏹️ 停止 IoT 設備模擬...')
        self.is_running = False

    def run_continuous(self, interval=5):
        """
        持續發送 IoT 數據，方便開發測試使用

        Args:
            interval: 發送間隔（秒），默認5秒
        """
        print(f'🔄 開始持續發送 IoT 數據 (間隔: {interval}秒)')
        print('按 Ctrl+C 停止')

        # 隨機啟動一些租借
        if self.bikes and self.members:
            num_to_rent = max(1, len(self.bikes) // 3)
            selected_bikes = random.sample(
                self.bikes, min(num_to_rent, len(self.bikes))
            )
            selected_members = random.sample(self.members, len(selected_bikes))

            for bike, member in zip(selected_bikes, selected_members):
                bike.start_rental(member)

        self.is_running = True
        cycle_count = 0

        try:
            while self.is_running:
                cycle_count += 1

                for bike in self.bikes:
                    # 移動腳踏車和更新狀態
                    bike.move()

                    # 模擬位置異常
                    bike.simulate_location_anomaly()

                    # 發送遙測資料
                    bike.send_telemetry()

                    # 錯誤場景模擬 (每5次循環)
                    if cycle_count % 5 == 0:
                        bike.simulate_error_scenarios()

                    # 隨機租借事件 (低機率)
                    if random.random() < 0.01:  # 1% 機率
                        if bike.is_rented:
                            bike.end_rental()
                        else:
                            if self.members:
                                member = random.choice(self.members)
                                bike.start_rental(member)

                print(
                    f"📡 循環 {cycle_count} 完成 - 已發送 {len(self.bikes)} 筆遙測數據 (租借中: {sum(1 for b in self.bikes if b.is_rented)}/{len(self.bikes)})"
                )
                time.sleep(interval)

        except KeyboardInterrupt:
            print('\n🛑 收到停止信號，正在結束...')
            self.stop_simulation()

        finally:
            # 結束所有租借
            for bike in self.bikes:
                if bike.is_rented:
                    bike.end_rental()
            print('✅ 持續發送已停止')


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description='IoT 設備模擬器')
    parser.add_argument('--bikes', type=int, default=3, help='模擬腳踏車數量 (預設: 3)')
    parser.add_argument('--duration', type=int, default=2, help='模擬持續時間(分鐘) (預設: 2)')
    parser.add_argument('--frequency', type=int, default=1, help='傳輸頻率(秒) (預設: 1)')
    parser.add_argument('--continuous', action='store_true', help='持續發送模式 (用於開發測試)')
    parser.add_argument('--interval', type=int, default=1, help='持續模式發送間隔(秒) (預設: 1)')
    parser.add_argument(
        '--test-errors', action='store_true', help='啟用錯誤場景測試模式 (增加錯誤機率)'
    )
    parser.add_argument('--error-only', action='store_true', help='僅測試錯誤場景 (不發送正常資料)')

    args = parser.parse_args()

    print('🧪 IoT 設備模擬器')
    print('=' * 60)

    simulator = IoTDeviceSimulator(
        num_bikes=args.bikes, test_errors=args.test_errors, error_only=args.error_only
    )

    try:
        if args.error_only:
            print(f'🧪 錯誤測試專用模式 ({args.duration}分鐘)')
            simulator.run_error_test_only(duration_minutes=args.duration)
        elif args.continuous:
            print(f'🔄 持續發送模式 (間隔: {args.interval}秒)')
            simulator.run_continuous(interval=args.interval)
        else:
            print(f'⏱️ 定時模擬模式 ({args.duration}分鐘)')
            simulator.start_simulation(duration_minutes=args.duration)
    except KeyboardInterrupt:
        print('\n⚠️ 收到中斷信號')
        simulator.stop_simulation()

    print('✨ 模擬完成')


if __name__ == '__main__':
    main()
