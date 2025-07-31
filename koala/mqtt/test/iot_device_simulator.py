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

import django

# 設置 Django 環境
sys.path.append('/usr/src/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')
django.setup()

from koala.mqtt import (
    mqtt_client,
    publish_bike_fleet_status,
    publish_bike_sport_metrics,
    publish_bike_telemetry,
)


class BikeSimulator:
    """腳踏車模擬器"""

    def __init__(self, bike_id):
        self.bike_id = bike_id
        self.is_running = False
        self.is_rented = False
        self.current_user = None
        self.session_start_time = None

        # 初始位置 (台北車站附近)
        self.lat = 25.0330 + random.uniform(-0.01, 0.01)
        self.lng = 121.5654 + random.uniform(-0.01, 0.01)

        # 腳踏車狀態
        self.battery_level = random.randint(60, 100)
        self.speed = 0
        self.last_maintenance = '2024-01-15'

        # 運動統計
        self.session_distance = 0
        self.session_calories = 0

    def start_rental(self, user_id):
        """開始租借"""
        self.is_rented = True
        self.current_user = user_id
        self.session_start_time = datetime.now()
        self.session_distance = 0
        self.session_calories = 0
        print(f"🚴 用戶 {user_id} 開始租借腳踏車 {self.bike_id}")

    def end_rental(self):
        """結束租借"""
        if self.is_rented:
            # 發送最終運動資料
            self.send_sport_metrics()

            print(f"🏁 用戶 {self.current_user} 結束租借腳踏車 {self.bike_id}")
            self.is_rented = False
            self.current_user = None
            self.session_start_time = None
            self.speed = 0

    def move(self):
        """模擬移動"""
        if self.is_rented:
            # 隨機移動
            self.lat += random.uniform(-0.0001, 0.0001)
            self.lng += random.uniform(-0.0001, 0.0001)

            # 隨機速度
            self.speed = random.uniform(5, 20)

            # 更新運動數據
            distance_increment = self.speed * (1 / 3600)  # 1秒的距離
            self.session_distance += distance_increment
            self.session_calories += distance_increment * 50  # 簡單的卡路里計算

            # 電池消耗
            if random.random() < 0.01:  # 1% 機率
                self.battery_level = max(0, self.battery_level - 1)
        else:
            self.speed = 0

    def send_telemetry(self):
        """發送遙測資料"""
        data = {
            'timestamp': int(time.time()),
            'latitude': round(self.lat, 6),
            'longitude': round(self.lng, 6),
            'battery_level': self.battery_level,
            'speed': round(self.speed, 1),
            'temperature': random.randint(20, 35),
            'voltage': round(random.uniform(11.8, 12.8), 2),
            'is_rented': self.is_rented,
            'current_user': self.current_user,
            'simulator': True,
        }

        success = publish_bike_telemetry(self.bike_id, data)
        if success:
            print(
                f"📡 {self.bike_id} 遙測資料已發送 (電池: {self.battery_level}%, 速度: {self.speed:.1f}km/h)"
            )
        return success

    def send_fleet_status(self):
        """發送車隊管理資料"""
        status = 'rented' if self.is_rented else 'available'
        if self.battery_level < 20:
            status = 'low_battery'
        elif self.battery_level < 5:
            status = 'maintenance'

        data = {
            'timestamp': int(time.time()),
            'status': status,
            'zone': f"zone_{random.randint(1, 5):02d}",
            'last_maintenance': self.last_maintenance,
            'rental_info': {
                'user_id': self.current_user,
                'start_time': int(self.session_start_time.timestamp())
                if self.session_start_time
                else None,
            }
            if self.is_rented
            else None,
            'parking_location': {
                'station_id': f"station_{random.randint(1, 10):03d}",
                'slot_number': random.randint(1, 20),
            }
            if not self.is_rented
            else None,
            'simulator': True,
        }

        success = publish_bike_fleet_status(self.bike_id, data)
        if success:
            print(f"🏢 {self.bike_id} 車隊狀態已發送 (狀態: {status})")
        return success

    def send_sport_metrics(self):
        """發送運動資料"""
        if not self.is_rented or not self.session_start_time:
            return False

        duration = int((datetime.now() - self.session_start_time).total_seconds())
        avg_speed = (self.session_distance / duration * 3600) if duration > 0 else 0

        data = {
            'timestamp': int(time.time()),
            'user_id': self.current_user,
            'session_id': f"session_{self.bike_id}_{int(self.session_start_time.timestamp())}",
            'distance': round(self.session_distance, 2),
            'duration': duration,
            'calories_burned': round(self.session_calories),
            'average_speed': round(avg_speed, 1),
            'max_speed': round(self.speed * 1.2, 1),  # 模擬最高速度
            'simulator': True,
        }

        success = publish_bike_sport_metrics(self.bike_id, data)
        if success:
            print(
                f"🏃 {self.bike_id} 運動資料已發送 (距離: {self.session_distance:.2f}km, 時間: {duration}s)"
            )
        return success


class IoTDeviceSimulator:
    """IoT 設備模擬器主類"""

    def __init__(self, num_bikes=5):
        self.bikes = []
        self.is_running = False

        # 初始化MQTT客戶端連接
        print('🔌 初始化MQTT客戶端連接...')
        if mqtt_client.connect():
            print('✅ MQTT客戶端連接成功')
        else:
            print('❌ MQTT客戶端連接失敗')

        # 建立腳踏車
        for i in range(num_bikes):
            bike_id = f"sim_bike_{i:03d}"
            self.bikes.append(BikeSimulator(bike_id))

        print(f"🚲 建立了 {num_bikes} 輛模擬腳踏車")

    def start_simulation(self, duration_minutes=10):
        """開始模擬"""
        print(f"🚀 開始 IoT 設備模擬 (持續 {duration_minutes} 分鐘)")

        self.is_running = True
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        # 隨機讓一些腳踏車開始租借
        num_to_rent = max(1, len(self.bikes) // 2)
        for bike in random.sample(self.bikes, min(num_to_rent, len(self.bikes))):
            user_id = f"sim_user_{random.randint(1000, 9999)}"
            bike.start_rental(user_id)

        cycle_count = 0

        while self.is_running and time.time() < end_time:
            cycle_count += 1

            for bike in self.bikes:
                # 移動腳踏車
                bike.move()

                # 發送遙測資料 (每次循環)
                bike.send_telemetry()

                # 發送車隊狀態 (每10次循環)
                if cycle_count % 10 == 0:
                    bike.send_fleet_status()

                # 發送運動資料 (每30次循環，且在租借中)
                if cycle_count % 30 == 0 and bike.is_rented:
                    bike.send_sport_metrics()

                # 隨機事件
                if random.random() < 0.005:  # 0.5% 機率
                    if bike.is_rented:
                        bike.end_rental()
                    else:
                        user_id = f"sim_user_{random.randint(1000, 9999)}"
                        bike.start_rental(user_id)

            print(f"⏰ 模擬循環 {cycle_count} 完成 (剩餘時間: {int(end_time - time.time())}秒)")
            time.sleep(5)  # 每5秒一個循環

        # 結束所有租借
        for bike in self.bikes:
            if bike.is_rented:
                bike.end_rental()

        # 斷開MQTT連接
        mqtt_client.disconnect()
        print('🔌 MQTT客戶端已斷開連接')
        print('🏁 IoT 設備模擬結束')

    def stop_simulation(self):
        """停止模擬"""
        print('⏹️ 停止 IoT 設備模擬...')
        self.is_running = False


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description='IoT 設備模擬器')
    parser.add_argument('--bikes', type=int, default=3, help='模擬腳踏車數量 (預設: 3)')
    parser.add_argument('--duration', type=int, default=5, help='模擬持續時間(分鐘) (預設: 5)')

    args = parser.parse_args()

    print('🧪 IoT 設備模擬器')
    print('=' * 60)

    simulator = IoTDeviceSimulator(num_bikes=args.bikes)

    try:
        simulator.start_simulation(duration_minutes=args.duration)
    except KeyboardInterrupt:
        print('\n⚠️ 收到中斷信號')
        simulator.stop_simulation()

    print('✨ 模擬完成')


if __name__ == '__main__':
    main()
