import random
from datetime import datetime

from django.utils import timezone

from bike.models import BikeInfo, BikeRealtimeStatus, BikeSeries
from scripts.base import BaseScript
from telemetry.models import TelemetryDevice


class CustomScript(BaseScript):
    def run(self):
        # 檢查是否已有 TelemetryDevice 資料
        if not TelemetryDevice.objects.exists():
            print('⚠️ 警告: 沒有找到遙測設備資料，請先執行 telemetry 腳本創建設備')
            return

        # 獲取所有系列
        urban_pro = BikeSeries.objects.get(series_name='Urban Pro')
        mountain_explorer = BikeSeries.objects.get(series_name='Mountain Explorer')
        city_cruiser = BikeSeries.objects.get(series_name='City Cruiser')
        classic_road = BikeSeries.objects.get(series_name='Classic Road')
        smart_scooter = BikeSeries.objects.get(series_name='Smart Scooter')
        compact_fold = BikeSeries.objects.get(series_name='Compact Fold')

        # 獲取可用的 TelemetryDevice (按順序分配)
        available_devices = list(TelemetryDevice.objects.filter(is_active=True))

        bikes_data = [
            # Urban Pro 系列
            {
                'bike_id': 'UP001',
                'bike_name': 'Urban Pro 001',
                'bike_model': 'UP-2024-001',
                'series': urban_pro,
            },
            {
                'bike_id': 'UP002',
                'bike_name': 'Urban Pro 002',
                'bike_model': 'UP-2024-002',
                'series': urban_pro,
            },
            {
                'bike_id': 'UP003',
                'bike_name': 'Urban Pro 003',
                'bike_model': 'UP-2024-003',
                'series': urban_pro,
            },
            # Mountain Explorer 系列
            {
                'bike_id': 'ME001',
                'bike_name': 'Mountain Explorer 001',
                'bike_model': 'ME-2024-001',
                'series': mountain_explorer,
            },
            {
                'bike_id': 'ME002',
                'bike_name': 'Mountain Explorer 002',
                'bike_model': 'ME-2024-002',
                'series': mountain_explorer,
            },
            # City Cruiser 系列
            {
                'bike_id': 'CC001',
                'bike_name': 'City Cruiser 001',
                'bike_model': 'CC-2024-001',
                'series': city_cruiser,
            },
            {
                'bike_id': 'CC002',
                'bike_name': 'City Cruiser 002',
                'bike_model': 'CC-2024-002',
                'series': city_cruiser,
            },
            # Classic Road 系列
            {
                'bike_id': 'CR001',
                'bike_name': 'Classic Road 001',
                'bike_model': 'CR-2024-001',
                'series': classic_road,
            },
            # Smart Scooter 系列
            {
                'bike_id': 'SS001',
                'bike_name': 'Smart Scooter 001',
                'bike_model': 'SS-2024-001',
                'series': smart_scooter,
            },
            # Compact Fold 系列
            {
                'bike_id': 'CF001',
                'bike_name': 'Compact Fold 001',
                'bike_model': 'CF-2024-001',
                'series': compact_fold,
            },
        ]

        if len(available_devices) < len(bikes_data):
            print(
                f"⚠️ 警告: 可用設備數量 ({len(available_devices)}) 少於車輛數量 ({len(bikes_data)})"
            )
            print('將只創建與設備數量相同的車輛')
            bikes_data = bikes_data[: len(available_devices)]

        bikes = []
        statuses = []

        # 台北市中心的經緯度範圍 (大約在台北車站周邊)
        base_lat = 25047000  # 25.047000 * 10^6
        base_lng = 121517000  # 121.517000 * 10^6

        for i, data in enumerate(bikes_data):
            # 分配對應的設備
            device = available_devices[i]
            bike = BikeInfo(telemetry_device=device, **data)
            bikes.append(bike)

            # 為每輛車創建即時狀態
            # 隨機生成在台北市中心附近的位置 (±0.01度範圍內)
            lat_offset = random.randint(-10000, 10000)  # ±0.01度
            lng_offset = random.randint(-10000, 10000)  # ±0.01度

            status = BikeRealtimeStatus(
                bike=bike,
                latitude=base_lat + lat_offset,
                longitude=base_lng + lng_offset,
                battery_level=random.randint(20, 100),
                status=random.choice(
                    [
                        BikeRealtimeStatus.STATUS_IDLE,
                        BikeRealtimeStatus.STATUS_IDLE,  # 增加閒置的機率
                        BikeRealtimeStatus.STATUS_MAINTENANCE,
                    ]
                ),
                last_seen=timezone.now(),
            )
            statuses.append(status)

        BikeInfo.objects.bulk_create(bikes, ignore_conflicts=True)
        BikeRealtimeStatus.objects.bulk_create(statuses, ignore_conflicts=True)

        print(f"成功創建 {len(bikes)} 輛車輛和對應的即時狀態")
        for bike in bikes:
            device_info = (
                f"設備: {bike.telemetry_device.IMEI}" if bike.telemetry_device else '無設備'
            )
            print(
                f"  - {bike.bike_id} ({bike.series.category.category_name} > {bike.series.series_name}): {device_info}"
            )

        print('\n車輛狀態分布：')
        status_counts = {}
        for status in statuses:
            status_name = (
                status.get_status_display()
                if hasattr(status, 'get_status_display')
                else status.status
            )
            status_counts[status_name] = status_counts.get(status_name, 0) + 1

        for status_name, count in status_counts.items():
            print(f"  - {status_name}: {count} 輛")
