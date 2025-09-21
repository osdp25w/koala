import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from django.contrib.gis.geos import Point
from django.utils import timezone

from account.models import Member
from bike.models import BikeInfo
from rental.models import BikeRental
from simulator.routes import TEST_ROUTES


class OSRMRouteService:
    """OSRM路線服務，獲取真實的路線座標"""

    OSRM_BASE_URL = 'http://host.docker.internal:5000/route/v1/driving'

    @classmethod
    def get_route_coordinates(
        cls, start_lat: float, start_lng: float, end_lat: float, end_lng: float
    ) -> Optional[List[Tuple[float, float]]]:
        """
        從OSRM獲取路線座標
        返回格式: [(lng, lat), (lng, lat), ...]
        """
        url = f"{cls.OSRM_BASE_URL}/{start_lng},{start_lat};{end_lng},{end_lat}"
        params = {'geometries': 'geojson', 'overview': 'full', 'steps': 'false'}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data['code'] != 'Ok' or not data['routes']:
                print(f"OSRM返回錯誤: {data.get('message', 'Unknown error')}")
                return None

            # 獲取路線幾何座標
            geometry = data['routes'][0]['geometry']['coordinates']
            return geometry  # OSRM返回的格式就是 [lng, lat]

        except Exception as e:
            print(f"調用OSRM API失敗: {e}")
            return None

    @classmethod
    def get_route_with_timing(
        cls, route_config: Dict, save_coordinates: bool = True
    ) -> Optional[List[Dict]]:
        """
        獲取帶時間戳的路線點
        返回格式: [{"lat": float, "lng": float, "timestamp": datetime}, ...]
        """
        start = route_config['start']
        end = route_config['end']
        duration_minutes = route_config['expected_duration_minutes']

        # 生成路線檔案名稱
        route_name = route_config['name'].replace('/', '_').replace(' ', '_')
        routes_dir = '/usr/src/app/simulator/routes'
        route_file = f"{routes_dir}/{route_name}.json"

        # 確保目錄存在
        os.makedirs(routes_dir, exist_ok=True)

        # 檢查是否已有快取的路線座標
        if os.path.exists(route_file):
            print(f"📁 使用快取路線: {route_config['name']}")
            with open(route_file, 'r', encoding='utf-8') as f:
                route_data = json.load(f)
                coordinates = route_data['coordinates']
        else:
            print(f"🌐 首次調用OSRM API: {route_config['name']}")
            coordinates = cls.get_route_coordinates(
                start['lat'], start['lng'], end['lat'], end['lng']
            )

            if not coordinates:
                return None

            # 儲存路線座標到檔案
            if save_coordinates:
                route_data = {
                    'route_name': route_config['name'],
                    'start_point': start,
                    'end_point': end,
                    'expected_duration_minutes': duration_minutes,
                    'total_coordinates': len(coordinates),
                    'coordinates': coordinates,
                    'created_at': timezone.now().isoformat(),
                    'osrm_api_called': True,
                }

                with open(route_file, 'w', encoding='utf-8') as f:
                    json.dump(route_data, f, ensure_ascii=False, indent=2)
                print(f"💾 路線座標已儲存: {route_file}")

        # 使用所有原始座標，不進行採樣
        sampled_coordinates = coordinates
        actual_duration_minutes = len(coordinates)  # 每個點1分鐘

        print(f"📍 路線詳情: {len(coordinates)} 個座標點，預計騎行時間 {actual_duration_minutes} 分鐘")

        start_time = timezone.now()
        route_points = []

        for i, (lng, lat) in enumerate(sampled_coordinates):
            timestamp = start_time + timedelta(minutes=i)  # 每1分鐘一個點
            route_points.append({'lat': lat, 'lng': lng, 'timestamp': timestamp})

        return route_points

    @classmethod
    def get_route_with_timing_from_start(
        cls, route_config: Dict, start_time: datetime, save_coordinates: bool = True
    ) -> Optional[List[Dict]]:
        """
        從指定開始時間獲取帶時間戳的路線點
        """
        # 複用現有邏輯，但使用自定義開始時間
        route_name = route_config['name'].replace('/', '_').replace(' ', '_')
        routes_dir = '/usr/src/app/simulator/routes'
        route_file = f"{routes_dir}/{route_name}.json"

        # 確保目錄存在
        os.makedirs(routes_dir, exist_ok=True)

        # 檢查是否已有快取的路線座標
        if os.path.exists(route_file):
            print(f"📁 使用快取路線: {route_config['name']}")
            with open(route_file, 'r', encoding='utf-8') as f:
                route_data = json.load(f)
                coordinates = route_data['coordinates']
        else:
            print(f"🌐 首次調用OSRM API: {route_config['name']}")
            start = route_config['start']
            end = route_config['end']
            coordinates = cls.get_route_coordinates(
                start['lat'], start['lng'], end['lat'], end['lng']
            )

            if not coordinates:
                return None

            # 儲存路線座標到檔案
            if save_coordinates:
                route_data = {
                    'route_name': route_config['name'],
                    'start_point': start,
                    'end_point': end,
                    'expected_duration_minutes': route_config[
                        'expected_duration_minutes'
                    ],
                    'total_coordinates': len(coordinates),
                    'coordinates': coordinates,
                    'created_at': start_time.isoformat(),
                    'osrm_api_called': True,
                }

                with open(route_file, 'w', encoding='utf-8') as f:
                    json.dump(route_data, f, ensure_ascii=False, indent=2)
                print(f"💾 路線座標已儲存: {route_file}")

        # 使用所有原始座標，不進行採樣
        sampled_coordinates = coordinates
        actual_duration_minutes = len(coordinates)  # 每個點1分鐘

        print(f"📍 路線詳情: {len(coordinates)} 個座標點，預計騎行時間 {actual_duration_minutes} 分鐘")

        route_points = []

        for i, (lng, lat) in enumerate(sampled_coordinates):
            timestamp = start_time + timedelta(minutes=i)  # 每1分鐘一個點
            route_points.append({'lat': lat, 'lng': lng, 'timestamp': timestamp})

        return route_points


class BikeRentalSimulator:
    """自行車租賃模擬器"""

    @classmethod
    def get_test_bikes(cls) -> List[BikeInfo]:
        """獲取測試用自行車（從 DataFactory 建立）"""
        bikes = BikeInfo.objects.filter(
            bike_id__startswith='SIMULATOR-HUALIEN'
        ).select_related('telemetry_device')
        if not bikes.exists():
            raise ValueError(
                '找不到測試自行車，請先執行: python simulator/scripts/setup_simulation_data.py'
            )
        return list(bikes)

    @classmethod
    def get_test_members(cls) -> List[Member]:
        """獲取測試用會員（從 DataFactory 建立）"""
        members = Member.objects.filter(username__startswith='SIMULATOR-member')
        if not members.exists():
            raise ValueError(
                '找不到測試會員，請先執行: python simulator/scripts/setup_simulation_data.py'
            )
        return list(members)

    @classmethod
    def simulate_rental_journey_with_time(
        cls,
        bike: BikeInfo,
        member: Member,
        route_config: Dict,
        start_time: datetime,
        simulation_errors: List = None,
    ) -> Optional[BikeRental]:
        """模擬一次完整的租賃行程（使用指定開始時間）"""
        from unittest.mock import patch

        # 使用指定的開始時間進行租車
        with patch('django.utils.timezone.now', return_value=start_time):
            # 1. 調用租車API創建租賃記錄
            rental = cls._call_rental_api(bike, member, simulation_errors)
            if not rental:
                return None

        print(f"開始租賃: {member.username} 租借 {bike.bike_id} - {route_config['name']}")

        # 2. 獲取路線座標（使用開始時間）
        route_points = OSRMRouteService.get_route_with_timing_from_start(
            route_config, start_time
        )
        if not route_points:
            print(f"無法獲取路線座標，使用預設路線")
            # 使用簡單的直線路線作為備用
            route_points = cls._generate_fallback_route_from_start(
                route_config, start_time
            )

        # 3. 模擬騎行過程 (發送IoT訊息)
        cls._simulate_iot_messages(bike, route_points, simulation_errors)

        # 4. 調用還車API結束租賃（使用路線結束時間）
        end_time = (
            route_points[-1]['timestamp']
            if route_points
            else start_time
            + timedelta(minutes=route_config['expected_duration_minutes'])
        )
        with patch('django.utils.timezone.now', return_value=end_time):
            updated_rental = cls._call_return_api(
                rental, route_config, simulation_errors
            )

        if updated_rental:
            print(
                f"租賃結束: {updated_rental.id} - 總時長: {updated_rental.end_time - updated_rental.start_time}"
            )
            return updated_rental
        else:
            print(f"❌ 還車失敗: {rental.id}")
            return rental

    @classmethod
    def simulate_rental_journey(
        cls,
        bike: BikeInfo,
        member: Member,
        route_config: Dict,
        simulation_errors: List = None,
    ) -> Optional[BikeRental]:
        """模擬一次完整的租賃行程"""

        # 1. 調用租車API創建租賃記錄
        rental = cls._call_rental_api(bike, member, simulation_errors)
        if not rental:
            return None

        print(f"開始租賃: {member.username} 租借 {bike.bike_id} - {route_config['name']}")

        # 2. 獲取路線座標
        route_points = OSRMRouteService.get_route_with_timing(route_config)
        if not route_points:
            print(f"無法獲取路線座標，使用預設路線")
            # 使用簡單的直線路線作為備用
            route_points = cls._generate_fallback_route(route_config)

        # 3. 模擬騎行過程 (發送IoT訊息)
        try:
            cls._simulate_iot_messages(bike, route_points, simulation_errors)
        except Exception as e:
            print(f"❌ IoT訊息模擬過程發生異常: {e}")
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'IOT_SIMULATION_ERROR',
                    'ERROR',
                    str(e),
                    f"車輛 {bike.bike_id} IoT模擬過程發生異常",
                )

        # 4. 調用還車API結束租賃
        updated_rental = cls._call_return_api(rental, route_config, simulation_errors)
        if updated_rental:
            print(
                f"租賃結束: {updated_rental.id} - 總時長: {updated_rental.end_time - updated_rental.start_time}"
            )
            return updated_rental
        else:
            print(f"❌ 還車失敗: {rental.id}")
            return rental

    @classmethod
    def _call_rental_api(
        cls, bike: BikeInfo, member: Member, simulation_errors: list = None
    ) -> Optional[BikeRental]:
        """調用租車API創建租賃記錄"""
        import json

        from rest_framework.test import APIClient

        try:
            # 創建API客戶端
            client = APIClient()

            # 模擬用戶認證
            client.force_authenticate(user=member.user)

            # 調用租車API
            response = client.post(
                '/api/rental/member/rentals/',
                data={'bike_id': bike.bike_id},
                format='json',
            )

            response_data = response.json()

            # 根據響應中的code字段判斷成功與否
            if response_data.get('code') == 2000:
                # API調用成功
                if 'data' in response_data and 'id' in response_data['data']:
                    rental_id = response_data['data']['id']
                    rental = BikeRental.objects.get(id=rental_id)
                    print(f"✅ 租車API調用成功: {rental.id}")
                    return rental
                else:
                    raise ValueError('API響應成功但找不到租賃ID')
            else:
                # API調用失敗（根據code判斷）
                error_msg = f"租車API調用失敗: code={response_data.get('code')}, msg={response_data.get('msg')}"
                print(f"❌ {error_msg}")
                if simulation_errors is not None:
                    SimulationRunner._record_simulation_error(
                        simulation_errors,
                        'RENTAL_API_ERROR',
                        'ERROR',
                        error_msg,
                        f"車輛 {bike.bike_id} 會員 {member.username} 租車API調用失敗",
                    )
                return None

        except Exception as e:
            error_msg = f"租車API調用異常: {str(e)}"
            print(f"❌ {error_msg}")
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'RENTAL_API_EXCEPTION',
                    'CRITICAL',
                    error_msg,
                    f"車輛 {bike.bike_id} 會員 {member.username} 租車API調用發生異常",
                )
            return None

    @classmethod
    def _call_return_api(
        cls, rental: BikeRental, route_config: Dict, simulation_errors: list = None
    ) -> Optional[BikeRental]:
        """調用還車API結束租賃"""
        from rest_framework.test import APIClient

        try:
            # 創建API客戶端
            client = APIClient()

            # 模擬用戶認證
            client.force_authenticate(user=rental.member.user)

            # 調用還車API
            response = client.patch(
                f'/api/rental/member/rentals/{rental.id}/',
                data={'action': 'return'},
                format='json',
            )

            response_data = response.json()

            # 根據響應中的code字段判斷成功與否
            if response_data.get('code') == 2000:
                rental.refresh_from_db()  # 重新載入資料庫中的數據
                print(f"✅ 還車API調用成功: {rental.id}")
                return rental
            else:
                error_msg = f"還車API調用失敗: code={response_data.get('code')}, msg={response_data.get('msg')}"
                print(f"❌ {error_msg}")
                if simulation_errors is not None:
                    SimulationRunner._record_simulation_error(
                        simulation_errors,
                        'RETURN_API_ERROR',
                        'ERROR',
                        error_msg,
                        f"租賃 {rental.id} 還車API調用失敗",
                    )
                return None

        except Exception as e:
            error_msg = f"還車API調用異常: {str(e)}"
            print(f"❌ {error_msg}")
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'RETURN_API_EXCEPTION',
                    'CRITICAL',
                    error_msg,
                    f"租賃 {rental.id} 還車API調用發生異常",
                )
            return None

    @classmethod
    def _generate_fallback_route_from_start(
        cls, route_config: Dict, start_time: datetime
    ) -> List[Dict]:
        """生成備用路線（直線插值，使用指定開始時間）"""
        start = route_config['start']
        end = route_config['end']
        duration_minutes = route_config['expected_duration_minutes']

        # 根據期望時間生成點數（每分鐘一個點）
        points_count = max(1, duration_minutes)

        route_points = []

        for i in range(points_count):
            ratio = i / (points_count - 1) if points_count > 1 else 0
            lat = start['lat'] + (end['lat'] - start['lat']) * ratio
            lng = start['lng'] + (end['lng'] - start['lng']) * ratio
            timestamp = start_time + timedelta(minutes=i)  # 每分鐘一個點

            route_points.append({'lat': lat, 'lng': lng, 'timestamp': timestamp})

        return route_points

    @classmethod
    def _generate_fallback_route(cls, route_config: Dict) -> List[Dict]:
        """生成備用路線（直線插值）"""
        start = route_config['start']
        end = route_config['end']
        duration_minutes = route_config['expected_duration_minutes']

        # 根據期望時間生成點數（每分鐘一個點）
        points_count = max(1, duration_minutes)

        route_points = []
        start_time = timezone.now()

        for i in range(points_count):
            ratio = i / (points_count - 1) if points_count > 1 else 0
            lat = start['lat'] + (end['lat'] - start['lat']) * ratio
            lng = start['lng'] + (end['lng'] - start['lng']) * ratio
            timestamp = start_time + timedelta(minutes=i)  # 每分鐘一個點

            route_points.append({'lat': lat, 'lng': lng, 'timestamp': timestamp})

        return route_points

    @classmethod
    def _simulate_iot_messages(
        cls, bike: BikeInfo, route_points: List[Dict], simulation_errors: list = None
    ):
        """模擬IoT訊息發送（包含錯誤模擬）"""
        from unittest.mock import patch

        from bike.models import BikeErrorLog, BikeRealtimeStatus
        from telemetry.models import TelemetryRecord

        # 獲取或創建BikeRealtimeStatus
        realtime_status, created = BikeRealtimeStatus.objects.get_or_create(
            bike=bike,
            defaults={
                'latitude': int(bike.realtime_status.latitude),
                'longitude': int(bike.realtime_status.longitude),
                'soc': bike.realtime_status.soc,
                'vehicle_speed': 0,
                'status': BikeRealtimeStatus.StatusOptions.RENTED,
                'last_seen': timezone.now(),
            },
        )

        print(f"📍 開始模擬 {len(route_points)} 個IoT點，預計時間跨度 {len(route_points)} 分鐘")

        for i, point in enumerate(route_points):
            # 使用 patch 設置當前時間點
            with patch('django.utils.timezone.now', return_value=point['timestamp']):
                try:
                    # 模擬各種錯誤情況
                    cls._simulate_random_errors(
                        bike, realtime_status, point, i, simulation_errors
                    )

                    # 準備座標和數據
                    # 統一精度到5位小數 (約10公尺精度)
                    lat_5decimal = round(point['lat'], 5)
                    lng_5decimal = round(point['lng'], 5)
                    latitude_int = int(lat_5decimal * 1000000)  # 轉換為整數格式
                    longitude_int = int(lng_5decimal * 1000000)
                    vehicle_speed = random.randint(8, 25)  # 模擬速度 8-25 km/h
                    current_timestamp = point['timestamp']

                    # 更新自行車即時狀態
                    realtime_status.latitude = latitude_int
                    realtime_status.longitude = longitude_int
                    realtime_status.vehicle_speed = vehicle_speed
                    realtime_status.last_seen = current_timestamp

                    # 模擬電量消耗
                    if random.random() < 0.15:  # 15%機率消耗電量
                        realtime_status.soc = max(0, realtime_status.soc - 1)

                    # 檢查電量過低 - 只記錄狀態，讓系統流程自動處理ErrorLog
                    if realtime_status.soc <= 10:
                        print(f"⚠️  電量過低: {bike.bike_id} 電量僅剩 {realtime_status.soc}%")

                    realtime_status.save()

                    # 創建 TelemetryRecord 記錄（統計服務需要這些數據）
                    TelemetryRecord.objects.create(
                        telemetry_device_imei=bike.telemetry_device.IMEI,
                        bike_id=bike.bike_id,
                        sequence_id=i + 1,
                        gps_time=current_timestamp,
                        rtc_time=current_timestamp,
                        send_time=current_timestamp,
                        created_at=current_timestamp,  # 明確設置創建時間為模擬時間
                        longitude=longitude_int,
                        latitude=latitude_int,
                        heading_direction=random.randint(0, 359),
                        vehicle_speed=vehicle_speed,
                        altitude=random.randint(0, 100),
                        gps_hdop=random.randint(5, 15),
                        gps_vdop=random.randint(5, 15),
                        satellites_count=random.randint(8, 12),
                        battery_voltage=random.randint(360, 420),
                        soc=realtime_status.soc,
                        bike_odometer=random.randint(1000, 50000),
                        assist_level=random.randint(0, 4),
                        pedal_torque=random.randint(50, 300),
                        controller_temp=random.randint(25, 45),
                        pedal_cadence=random.randint(40, 120),
                        battery_temp1=random.randint(20, 40),
                        battery_temp2=random.randint(20, 40),
                        acc_status=True,
                        output_status=1,
                        analog_input=random.randint(1000, 5000),
                        backup_battery=random.randint(120, 140),
                        rssi=random.randint(15, 31),
                        total_odometer=random.randint(10000, 100000),
                        member_id='',
                        report_id=1,
                    )

                    if i % 10 == 0 or i == len(route_points) - 1:  # 每10個點或最後一個點輸出
                        print(
                            f"IoT: {bike.bike_id} at ({point['lat']:.6f}, {point['lng']:.6f}) "
                            f"SOC: {realtime_status.soc}% 速度: {realtime_status.vehicle_speed}km/h "
                            f"時間: {point['timestamp'].strftime('%H:%M:%S')} [{i+1}/{len(route_points)}]"
                        )

                except Exception as e:
                    # 捕獲任何IoT傳輸錯誤 - 讓系統流程自動處理ErrorLog
                    print(f"❌ IoT傳輸錯誤: {bike.bike_id} - {str(e)}")

        # 租賃結束狀態會由還車API處理，這裡只重置速度
        realtime_status.vehicle_speed = 0
        realtime_status.save()

    @classmethod
    def _simulate_random_errors(
        cls,
        bike: BikeInfo,
        realtime_status,
        point: Dict,
        point_index: int,
        simulation_errors: list = None,
    ):
        """模擬隨機錯誤事件"""
        from bike.models import BikeErrorLog

        # 總錯誤機率 5%
        if random.random() >= 0.05:
            return  # 95%機率無錯誤

        # 發生錯誤時，按權重隨機選擇錯誤類型
        error_types = [
            ('GPS_SIGNAL_LOST', 2),
            ('IOT_DEVICE_MALFUNCTION', 1),
            ('ABNORMAL_SPEED', 5),
            ('HIGH_BATTERY_TEMP', 3),
            ('COMMUNICATION_DELAY', 8),
        ]

        # 計算總權重
        total_weight = sum(weight for _, weight in error_types)

        # 隨機選擇錯誤類型
        rand_val = random.uniform(0, total_weight)
        cumulative_weight = 0

        for error_code, weight in error_types:
            cumulative_weight += weight
            if rand_val <= cumulative_weight:
                selected_error = error_code
                break
        else:
            selected_error = error_types[-1][0]  # 備用選擇

        # 根據選擇的錯誤類型模擬異常狀態，讓系統流程自動處理
        if selected_error == 'GPS_SIGNAL_LOST':
            print(f"🛰️ GPS訊號異常: {bike.bike_id} 座標可能不準確")
            # 模擬GPS座標偏移
            point['lat'] += random.uniform(-0.001, 0.001)
            point['lng'] += random.uniform(-0.001, 0.001)
            # 記錄錯誤事件
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'GPS_SIGNAL_LOST',
                    'WARNING',
                    f"GPS訊號異常: {bike.bike_id} 座標偏移",
                    f"車輛 {bike.bike_id} 在路線點 {point_index} 處GPS訊號不穩定，座標發生偏移",
                )

        elif selected_error == 'IOT_DEVICE_MALFUNCTION':
            print(f"📡 IoT設備故障: {bike.bike_id} 設備異常")
            # 記錄錯誤事件
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'IOT_DEVICE_MALFUNCTION',
                    'CRITICAL',
                    f"IoT設備故障: {bike.bike_id} 設備無法正常運作",
                    f"車輛 {bike.bike_id} 的IoT設備 {bike.telemetry_device.IMEI if bike.telemetry_device else 'Unknown'} 發生故障",
                )
            # 設備故障時暫停狀態更新，讓Exception觸發錯誤處理流程
            raise Exception(
                f"IoT設備故障: {bike.telemetry_device.IMEI if bike.telemetry_device else 'Unknown'}"
            )

        elif selected_error == 'ABNORMAL_SPEED':
            abnormal_speed = random.randint(40, 60)  # 異常高速
            print(f"⚡ 異常速度: {bike.bike_id} 檢測到 {abnormal_speed} km/h")
            # 可以修改realtime_status的速度來反映異常狀態
            realtime_status.vehicle_speed = abnormal_speed
            # 記錄錯誤事件
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'ABNORMAL_SPEED',
                    'WARNING',
                    f"異常速度: {bike.bike_id} 檢測到 {abnormal_speed} km/h",
                    f"車輛 {bike.bike_id} 在路線點 {point_index} 處速度異常，超出正常範圍",
                )

        elif selected_error == 'HIGH_BATTERY_TEMP':
            high_temp = random.randint(45, 60)
            print(f"🌡️ 電池溫度異常: {bike.bike_id} 溫度 {high_temp}°C")
            # 這裡可以設置相關的溫度狀態標記
            # 記錄錯誤事件
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'HIGH_BATTERY_TEMP',
                    'ERROR',
                    f"電池溫度異常: {bike.bike_id} 溫度 {high_temp}°C",
                    f"車輛 {bike.bike_id} 在路線點 {point_index} 處電池溫度過高，可能影響性能",
                )

        elif selected_error == 'COMMUNICATION_DELAY':
            delay_seconds = random.randint(30, 120)
            print(f"📶 通訊延遲: {bike.bike_id} 延遲 {delay_seconds} 秒")
            # 可以延遲更新時間戳來模擬通訊延遲
            import time

            time.sleep(min(delay_seconds / 100, 2))  # 實際模擬中縮短延遲時間
            # 記錄錯誤事件
            if simulation_errors is not None:
                SimulationRunner._record_simulation_error(
                    simulation_errors,
                    'COMMUNICATION_DELAY',
                    'INFO',
                    f"通訊延遲: {bike.bike_id} 延遲 {delay_seconds} 秒",
                    f"車輛 {bike.bike_id} 在路線點 {point_index} 處網路通訊發生延遲",
                )


class SimulationRunner:
    """模擬運行器"""

    @classmethod
    def run_full_simulation(cls, num_rentals: int = 20):
        """運行完整模擬"""
        print('=' * 50)
        print('開始花蓮自行車租賃模擬')
        print('=' * 50)

        # 0. 記錄模擬前的基線狀態
        print('0. 記錄模擬前基線狀態...')
        baseline_stats = cls._capture_baseline_statistics()

        # 1. 獲取測試數據
        print('\n1. 載入測試自行車和會員...')
        bikes = BikeRentalSimulator.get_test_bikes()
        members = BikeRentalSimulator.get_test_members()

        print(f"載入了 {len(bikes)} 輛自行車和 {len(members)} 個會員")

        # 2. 初始化路線統計和錯誤事件記錄
        route_usage = {}
        simulation_errors = []  # 記錄模擬過程中的錯誤事件

        # 追蹤每台自行車的租賃時間，確保不重疊
        bike_availability = {}  # {bike_id: next_available_time}
        current_simulation_time = timezone.now()  # 模擬開始時間

        # 3. 執行租賃模擬
        print('\n3. 開始租賃模擬...')
        rentals = []

        for i in range(num_rentals):
            # 1. 先篩選物理上可用的自行車
            physically_available_bikes = [
                bike
                for bike in bikes
                if hasattr(bike, 'realtime_status')
                and bike.realtime_status.status
                == bike.realtime_status.StatusOptions.IDLE
                and bike.realtime_status.get_is_rentable()
            ]

            if not physically_available_bikes:
                print(f"沒有物理可用的自行車，模擬在第 {i+1} 次租賃時停止")
                break

            # 2. 篩選時間上可用的自行車（考慮租賃連續性）
            time_available_bikes = []
            for bike in physically_available_bikes:
                next_available = bike_availability.get(
                    bike.bike_id, current_simulation_time
                )
                if current_simulation_time >= next_available:
                    time_available_bikes.append(bike)

            if not time_available_bikes:
                # 如果沒有時間可用的自行車，將模擬時間推進到最早可用時間
                earliest_available = min(
                    bike_availability.get(bike.bike_id, current_simulation_time)
                    for bike in physically_available_bikes
                )
                current_simulation_time = earliest_available
                print(
                    f"⏰ 推進模擬時間到 {current_simulation_time.strftime('%H:%M:%S')} 等待自行車可用"
                )
                time_available_bikes = physically_available_bikes

            # 3. 從時間可用車輛中隨機選擇
            bike = random.choice(time_available_bikes)
            member = random.choice(members)
            route = random.choice(TEST_ROUTES)

            # 4. 計算這次租賃的時間跨度
            route_name = route['name']
            route_duration_minutes = (
                len(route.get('coordinates', []))
                if 'coordinates' in route
                else route['expected_duration_minutes']
            )
            rental_end_time = current_simulation_time + timedelta(
                minutes=route_duration_minutes
            )

            print(f"\n租賃 #{i+1}: {member.username} 租借 {bike.bike_id} - {route_name}")
            print(
                f"🕒 模擬時間: {current_simulation_time.strftime('%H:%M:%S')} → {rental_end_time.strftime('%H:%M:%S')} ({route_duration_minutes}分鐘)"
            )

            try:
                rental = BikeRentalSimulator.simulate_rental_journey_with_time(
                    bike, member, route, current_simulation_time, simulation_errors
                )
                if rental:
                    rentals.append(rental)
                    # 只有租賃成功才記錄路線使用次數
                    route_usage[route_name] = route_usage.get(route_name, 0) + 1

                # 6. 更新自行車可用時間（租賃結束後10分鐘才能再次租借，模擬清潔整理時間）
                bike_availability[bike.bike_id] = rental_end_time + timedelta(
                    minutes=10
                )

                # 7. 推進模擬時間（每次租賃間隔30分鐘，模擬不同用戶的租賃間隔）
                current_simulation_time = rental_end_time + timedelta(minutes=30)

            except Exception as e:
                print(f"租賃過程發生錯誤: {e}")
                # 記錄租賃層級的錯誤
                cls._record_simulation_error(
                    simulation_errors,
                    'RENTAL_PROCESS_ERROR',
                    'CRITICAL',
                    f"租賃過程失敗: {str(e)}",
                    f"車輛 {bike.bike_id} 會員 {member.username} 路線 {route['name']} 租賃過程中發生嚴重錯誤",
                )
                # 發生錯誤時，自行車狀態會由API調用失敗自動處理，無需手動設置

        print(f"\n模擬完成! 總共完成 {len(rentals)} 次租賃")

        # 4. 觸發統計計算
        print('\n4. 觸發統計計算...')
        cls._trigger_statistics_calculation()

        # 5. 觸發失敗座標重試任務
        print('\n5. 處理失敗的座標同步...')
        cls._trigger_coordinate_retry()

        # 6. 記錄模擬後狀態並比較差異
        print('\n6. 分析模擬結果...')
        final_stats = cls._capture_baseline_statistics()
        cls._show_simulation_impact(
            baseline_stats, final_stats, route_usage, simulation_errors
        )

        print('\n' + '=' * 50)
        print('花蓮自行車租賃模擬結束')
        print('=' * 50)

        return rentals

    @classmethod
    def _record_simulation_error(
        cls,
        simulation_errors: list,
        error_code: str,
        level: str,
        message: str,
        reason: str,
    ):
        """記錄模擬過程中的錯誤事件"""
        error_event = {
            'timestamp': timezone.now(),
            'error_code': error_code,
            'level': level,
            'message': message,
            'reason': reason,
        }
        simulation_errors.append(error_event)
        print(f"❌ 錯誤事件記錄: [{level}] {error_code} - {message}")

    @classmethod
    def _capture_baseline_statistics(cls):
        """記錄模擬前的基線統計數據"""
        from bike.models import BikeErrorLog
        from rental.models import BikeRental
        from statistic.models import (
            DailyGeometryCoordinateStatistics,
            GeometryCoordinate,
            HourlyGeometryCoordinateStatistics,
            RideSession,
            RouteMatchResult,
        )

        stats = {
            'timestamp': timezone.now(),
            'bike_rentals': BikeRental.objects.count(),
            'ride_sessions': RideSession.objects.count(),
            'route_match_results': RouteMatchResult.objects.count(),
            'geometry_coordinates': GeometryCoordinate.objects.count(),
            'hourly_geo_stats': HourlyGeometryCoordinateStatistics.objects.count(),
            'daily_geo_stats': DailyGeometryCoordinateStatistics.objects.count(),
            'error_logs_total': BikeErrorLog.objects.count(),
            'error_logs_today': BikeErrorLog.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'error_logs_by_level': {
                level[0]: BikeErrorLog.objects.filter(level=level[0]).count()
                for level in BikeErrorLog.LevelOptions.choices
            },
        }

        print('📊 當前資料庫狀態:')
        print(f"  • 租賃記錄: {stats['bike_rentals']} 筆")
        print(f"  • 騎行軌跡: {stats['ride_sessions']} 筆")
        print(f"  • 路線匹配結果: {stats['route_match_results']} 筆")
        print(f"  • 幾何座標: {stats['geometry_coordinates']} 筆")
        print(f"  • 小時級別座標統計: {stats['hourly_geo_stats']} 筆")
        print(f"  • 日級別座標統計: {stats['daily_geo_stats']} 筆")
        print(f"  • 錯誤日誌(總計): {stats['error_logs_total']} 筆")
        print(f"  • 錯誤日誌(今日): {stats['error_logs_today']} 筆")

        # 保存 baseline 統計到文件
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        reports_dir = '/usr/src/app/simulator/reports'
        os.makedirs(reports_dir, exist_ok=True)
        baseline_file = f"{reports_dir}/baseline_stats_{timestamp}.json"

        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
        print(f"📄 Baseline統計已保存: {baseline_file}")

        return stats

    @classmethod
    def _show_simulation_impact(
        cls,
        baseline_stats: dict,
        final_stats: dict,
        route_usage: dict = None,
        simulation_errors: list = None,
    ):
        """顯示模擬對系統的影響"""
        print('📈 模擬影響分析:')
        print('=' * 40)

        # 生成報告檔案
        report_data = cls._generate_simulation_report(
            baseline_stats, final_stats, route_usage, simulation_errors
        )

        # 計算增量
        changes = {
            'bike_rentals': final_stats['bike_rentals']
            - baseline_stats['bike_rentals'],
            'ride_sessions': final_stats['ride_sessions']
            - baseline_stats['ride_sessions'],
            'route_match_results': final_stats['route_match_results']
            - baseline_stats['route_match_results'],
            'geometry_coordinates': final_stats['geometry_coordinates']
            - baseline_stats['geometry_coordinates'],
            'hourly_geo_stats': final_stats['hourly_geo_stats']
            - baseline_stats['hourly_geo_stats'],
            'daily_geo_stats': final_stats['daily_geo_stats']
            - baseline_stats['daily_geo_stats'],
            'error_logs_total': final_stats['error_logs_total']
            - baseline_stats['error_logs_total'],
            'error_logs_today': final_stats['error_logs_today']
            - baseline_stats['error_logs_today'],
        }

        print('🔢 數據增量:')
        for key, change in changes.items():
            name_map = {
                'bike_rentals': '租賃記錄',
                'ride_sessions': '騎行軌跡',
                'route_match_results': '路線匹配結果',
                'geometry_coordinates': '幾何座標',
                'hourly_geo_stats': '小時級別座標統計',
                'daily_geo_stats': '日級別座標統計',
                'error_logs_total': '錯誤日誌(總計)',
                'error_logs_today': '錯誤日誌(今日)',
            }
            if change > 0:
                print(f"  ✅ {name_map[key]}: +{change} 筆")
            elif change == 0:
                print(f"  ➖ {name_map[key]}: 無變化")
            else:
                print(f"  ❌ {name_map[key]}: {change} 筆 (異常)")

        # 錯誤日誌詳細分析
        if changes['error_logs_today'] > 0:
            print(f"\n🚨 新增錯誤日誌分析:")
            cls._show_new_error_analysis(baseline_stats['timestamp'])

        # 座標統計分析
        if changes['geometry_coordinates'] > 0:
            print(f"\n🗺️ 新增座標點: {changes['geometry_coordinates']} 個")
            print(
                f"  • 平均每次租賃產生座標: {changes['geometry_coordinates'] / max(1, changes['bike_rentals']):.1f} 個"
            )

        # 統計效率分析
        print(f"\n⚡ 統計處理效率:")
        print(
            f"  • 騎行軌跡處理率: {changes['ride_sessions'] / max(1, changes['bike_rentals']) * 100:.1f}%"
        )
        print(
            f"  • 路線匹配成功率: {changes['route_match_results'] / max(1, changes['ride_sessions']) * 100:.1f}%"
        )

        # 路線使用統計
        if route_usage:
            print(f"\n🗺️ 路線使用統計:")
            sorted_routes = sorted(
                route_usage.items(), key=lambda x: x[1], reverse=True
            )
            for route_name, count in sorted_routes:
                print(f"  • {route_name}: {count} 次")

        # 模擬錯誤事件統計
        if simulation_errors:
            print(f"\n❌ 模擬錯誤事件統計:")
            print(f"  • 總錯誤事件: {len(simulation_errors)} 個")

            # 按錯誤級別統計
            error_levels = {}
            error_codes = {}
            for error in simulation_errors:
                level = error['level']
                code = error['error_code']
                error_levels[level] = error_levels.get(level, 0) + 1
                error_codes[code] = error_codes.get(code, 0) + 1

            print(f"  • 錯誤級別分佈:")
            level_emojis = {'CRITICAL': '🔴', 'ERROR': '🟠', 'WARNING': '🟡', 'INFO': '🔵'}
            for level, count in sorted(
                error_levels.items(), key=lambda x: x[1], reverse=True
            ):
                emoji = level_emojis.get(level, '⚪')
                print(f"    {emoji} {level}: {count} 次")

            print(f"  • 錯誤類型分佈:")
            for code, count in sorted(
                error_codes.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"    • {code}: {count} 次")

        print(f"\n📄 詳細報告已儲存: {report_data['report_file']}")

    @classmethod
    def _show_new_error_analysis(cls, baseline_time):
        """分析新增的錯誤日誌"""
        from django.db.models import Count

        from bike.models import BikeErrorLog

        new_errors = BikeErrorLog.objects.filter(created_at__gte=baseline_time)

        if not new_errors.exists():
            return

        # 按錯誤等級統計
        level_stats = (
            new_errors.values('level').annotate(count=Count('level')).order_by('-count')
        )
        for stat in level_stats:
            level_name = dict(BikeErrorLog.LevelOptions.choices)[stat['level']]
            emoji = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(
                stat['level'], '⚪'
            )
            print(f"    {emoji} {level_name}: {stat['count']} 筆")

        # 按錯誤類型統計
        code_stats = (
            new_errors.values('code').annotate(count=Count('code')).order_by('-count')
        )
        print(f"    錯誤類型分佈:")
        for stat in code_stats:
            print(f"      • {stat['code']}: {stat['count']} 筆")

    @classmethod
    def _generate_simulation_report(
        cls,
        baseline_stats: dict,
        final_stats: dict,
        route_usage: dict = None,
        simulation_errors: list = None,
    ):
        """生成模擬報告並儲存到檔案"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        reports_dir = '/usr/src/app/simulator/reports'
        os.makedirs(reports_dir, exist_ok=True)
        report_file = f"{reports_dir}/simulation_report_{timestamp}.json"

        # 計算增量
        changes = {
            'bike_rentals': final_stats['bike_rentals']
            - baseline_stats['bike_rentals'],
            'ride_sessions': final_stats['ride_sessions']
            - baseline_stats['ride_sessions'],
            'route_match_results': final_stats['route_match_results']
            - baseline_stats['route_match_results'],
            'geometry_coordinates': final_stats['geometry_coordinates']
            - baseline_stats['geometry_coordinates'],
            'hourly_geo_stats': final_stats['hourly_geo_stats']
            - baseline_stats['hourly_geo_stats'],
            'daily_geo_stats': final_stats['daily_geo_stats']
            - baseline_stats['daily_geo_stats'],
            'error_logs_total': final_stats['error_logs_total']
            - baseline_stats['error_logs_total'],
            'error_logs_today': final_stats['error_logs_today']
            - baseline_stats['error_logs_today'],
        }

        # 計算效率指標
        efficiency_metrics = {
            'ride_session_processing_rate': changes['ride_sessions']
            / max(1, changes['bike_rentals'])
            * 100,
            'route_matching_success_rate': changes['route_match_results']
            / max(1, changes['ride_sessions'])
            * 100,
            'avg_coordinates_per_rental': changes['geometry_coordinates']
            / max(1, changes['bike_rentals']),
        }

        # 分析錯誤事件統計
        error_summary = {}
        if simulation_errors:
            error_summary = {
                'total_errors': len(simulation_errors),
                'errors_by_level': {},
                'errors_by_code': {},
                'first_error_time': min(err['timestamp'] for err in simulation_errors)
                if simulation_errors
                else None,
                'last_error_time': max(err['timestamp'] for err in simulation_errors)
                if simulation_errors
                else None,
            }

            # 按級別統計
            for error in simulation_errors:
                level = error['level']
                code = error['error_code']
                error_summary['errors_by_level'][level] = (
                    error_summary['errors_by_level'].get(level, 0) + 1
                )
                error_summary['errors_by_code'][code] = (
                    error_summary['errors_by_code'].get(code, 0) + 1
                )

        report_data = {
            'simulation_info': {
                'timestamp': timezone.now().isoformat(),
                'simulation_duration': str(
                    final_stats['timestamp'] - baseline_stats['timestamp']
                ),
                'total_rentals': changes['bike_rentals'],
            },
            'baseline_statistics': baseline_stats,
            'final_statistics': final_stats,
            'changes': changes,
            'efficiency_metrics': efficiency_metrics,
            'route_usage': route_usage or {},
            'route_usage_summary': {
                'total_routes_used': len(route_usage) if route_usage else 0,
                'most_popular_route': max(route_usage.items(), key=lambda x: x[1])
                if route_usage
                else None,
                'least_popular_route': min(route_usage.items(), key=lambda x: x[1])
                if route_usage
                else None,
            },
            'simulation_errors': {
                'error_events': [
                    {
                        'timestamp': err['timestamp'].isoformat(),
                        'error_code': err['error_code'],
                        'level': err['level'],
                        'message': err['message'],
                        'reason': err['reason'],
                    }
                    for err in (simulation_errors or [])
                ],
                'error_summary': error_summary,
            },
        }

        # 儲存報告
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

        return {'report_file': report_file, 'report_data': report_data}

    @classmethod
    def _show_error_statistics(cls):
        """顯示錯誤日誌統計"""
        from django.db.models import Count

        from bike.models import BikeErrorLog

        # 取得今天產生的錯誤日誌
        today = timezone.now().date()
        today_errors = BikeErrorLog.objects.filter(created_at__date=today)

        if not today_errors.exists():
            print('✅ 今日無錯誤記錄')
            return

        print(f"📊 今日錯誤統計 (共 {today_errors.count()} 筆):")

        # 按錯誤等級統計
        level_stats = (
            today_errors.values('level')
            .annotate(count=Count('level'))
            .order_by('-count')
        )
        for stat in level_stats:
            level_name = dict(BikeErrorLog.LevelOptions.choices)[stat['level']]
            emoji = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(
                stat['level'], '⚪'
            )
            print(f"  {emoji} {level_name}: {stat['count']} 筆")

        # 按錯誤類型統計
        print('\n📋 錯誤類型分佈:')
        code_stats = (
            today_errors.values('code', 'title')
            .annotate(count=Count('code'))
            .order_by('-count')
        )
        for stat in code_stats:
            print(f"  • {stat['title']} ({stat['code']}): {stat['count']} 筆")

        # 按自行車統計
        print('\n🚲 問題車輛:')
        bike_stats = (
            today_errors.values('bike__bike_id')
            .annotate(count=Count('bike'))
            .order_by('-count')[:5]
        )
        for stat in bike_stats:
            print(f"  • {stat['bike__bike_id']}: {stat['count']} 筆錯誤")

    @classmethod
    def _trigger_statistics_calculation(cls):
        """觸發統計計算（基於模擬時間流）"""
        try:
            from datetime import datetime, timedelta

            from statistic.tasks import (
                calculate_daily_statistics,
                calculate_hourly_statistics,
            )

            print('🔄 根據模擬時間流觸發統計計算...')

            # 獲取模擬時間範圍（從最早到最晚的TelemetryRecord）
            from django.db import models as django_models

            from telemetry.models import TelemetryRecord

            time_range = TelemetryRecord.objects.aggregate(
                start_time=django_models.Min('gps_time'),
                end_time=django_models.Max('gps_time'),
            )

            if not time_range['start_time'] or not time_range['end_time']:
                print('⚠️ 沒有找到TelemetryRecord數據，跳過統計計算')
                return

            start_time = time_range['start_time']
            end_time = time_range['end_time']

            print(f"📅 模擬時間範圍: {start_time} 到 {end_time}")

            # 觸發每小時統計（涵蓋整個模擬時間範圍）
            current_hour = start_time.replace(minute=0, second=0, microsecond=0)
            while current_hour <= end_time:
                try:
                    print(f"⏱️ 觸發小時統計: {current_hour}")
                    # 同步調用而不是異步，確保在模擬結束前完成
                    calculate_hourly_statistics.apply(args=[current_hour.isoformat()])
                except Exception as hour_error:
                    print(f"❌ 小時統計失敗 {current_hour}: {hour_error}")

                current_hour += timedelta(hours=1)

            # 觸發每日統計（涵蓋整個模擬日期範圍）
            current_date = start_time.date()
            end_date = end_time.date()
            while current_date <= end_date:
                try:
                    print(f"📊 觸發日統計: {current_date}")
                    calculate_daily_statistics.apply(
                        args=[current_date.strftime('%Y-%m-%d')]
                    )
                except Exception as day_error:
                    print(f"❌ 日統計失敗 {current_date}: {day_error}")

                current_date += timedelta(days=1)

            print('✅ 統計計算觸發完成')

        except Exception as e:
            print(f"統計計算錯誤: {e}")

    @classmethod
    def _trigger_coordinate_retry(cls):
        """觸發失敗座標重試任務"""
        try:
            from statistic.models import RouteMatchResult
            from statistic.tasks import retry_failed_coordinate_sync

            # 檢查是否有需要重試的座標同步
            failed_count = RouteMatchResult.objects.filter(
                is_sync_geometry_coordinate=False, resync_details__isnull=False
            ).count()

            if failed_count == 0:
                print('✅ 沒有需要重試的座標同步')
                return

            print(f"🔄 發現 {failed_count} 個失敗的座標同步，觸發重試任務...")

            # 同步執行重試任務，確保在模擬報告前完成
            result = retry_failed_coordinate_sync.apply()

            if result.successful():
                retry_result = result.result
                print(
                    f"✅ 座標重試完成: 處理 {retry_result['processed']} 個, "
                    f"成功 {retry_result['success']} 個, 失敗 {retry_result['failed']} 個"
                )
            else:
                print(f"❌ 座標重試任務失敗: {result.traceback}")

        except Exception as e:
            print(f"❌ 觸發座標重試失敗: {e}")
