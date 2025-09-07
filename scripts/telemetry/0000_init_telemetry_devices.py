from scripts.base import BaseScript
from telemetry.models import TelemetryDevice


class CustomScript(BaseScript):
    def run(self):
        # 創建預設的遙測設備資料
        # 獨立創建設備，不依賴車輛資料

        devices_data = [
            # Urban Pro 系列設備
            {
                'IMEI': '867295075673001',
                'name': 'Urban Pro Device 001',
                'bike_series': 'Urban Pro',
            },
            {
                'IMEI': '867295075673002',
                'name': 'Urban Pro Device 002',
                'bike_series': 'Urban Pro',
            },
            {
                'IMEI': '867295075673003',
                'name': 'Urban Pro Device 003',
                'bike_series': 'Urban Pro',
            },
            # Mountain Explorer 系列設備
            {
                'IMEI': '867295075673011',
                'name': 'Mountain Explorer Device 001',
                'bike_series': 'Mountain Explorer',
            },
            {
                'IMEI': '867295075673012',
                'name': 'Mountain Explorer Device 002',
                'bike_series': 'Mountain Explorer',
            },
            # City Cruiser 系列設備
            {
                'IMEI': '867295075673021',
                'name': 'City Cruiser Device 001',
                'bike_series': 'City Cruiser',
            },
            {
                'IMEI': '867295075673022',
                'name': 'City Cruiser Device 002',
                'bike_series': 'City Cruiser',
            },
            # Classic Road 系列設備
            {
                'IMEI': '867295075673031',
                'name': 'Classic Road Device 001',
                'bike_series': 'Classic Road',
            },
            # Smart Scooter 系列設備
            {
                'IMEI': '867295075673041',
                'name': 'Smart Scooter Device 001',
                'bike_series': 'Smart Scooter',
            },
            # Compact Fold 系列設備
            {
                'IMEI': '867295075673051',
                'name': 'Compact Fold Device 001',
                'bike_series': 'Compact Fold',
            },
        ]

        devices = []
        for data in devices_data:
            device = TelemetryDevice(
                IMEI=data['IMEI'],
                name=data['name'],
                model='TD-2024-IoT',  # 統一的遙測設備型號
                is_active=True,
            )
            devices.append(device)

        TelemetryDevice.objects.bulk_create(devices, ignore_conflicts=True)

        print(f"成功創建 {len(devices)} 個遙測設備")
        for device in devices:
            print(f"  - {device.IMEI}: {device.name} ({device.model})")

        print(f"\n設備狀態:")
        active_count = len([d for d in devices if d.is_active])
        inactive_count = len(devices) - active_count
        print(f"  - 啟用: {active_count} 個")
        print(f"  - 停用: {inactive_count} 個")
