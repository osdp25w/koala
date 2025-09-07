import random
from datetime import datetime, timedelta

from django.utils import timezone

from account.models import Member
from bike.models import BikeInfo
from scripts.base import BaseScript
from telemetry.models import TelemetryDevice, TelemetryRecord


class CustomScript(BaseScript):
    def run(self):
        # 獲取已存在的設備、車輛和會員
        devices = TelemetryDevice.objects.filter(is_active=True)
        bikes = BikeInfo.objects.filter(is_active=True)
        members = Member.objects.filter(is_active=True)

        if not devices.exists():
            print('⚠️ 警告: 沒有找到遙測設備，請先執行 telemetry devices 腳本')
            return

        if not bikes.exists():
            print('⚠️ 警告: 沒有找到車輛資料，請先執行 bike 腳本')
            return

        records = []

        # 為每個設備創建一些測試記錄 (最近24小時內的數據)
        base_time = timezone.now()

        # 台北市中心的經緯度範圍
        base_lat = 25047000  # 25.047000 * 10^6
        base_lng = 121517000  # 121.517000 * 10^6

        for device in devices[:5]:  # 只為前5個設備創建記錄，避免數據量過大
            try:
                bike = bikes.get(telemetry_device=device)

                # 為每個設備創建 10-20 條記錄
                record_count = random.randint(10, 20)

                for i in range(record_count):
                    # 時間遞減（最新的記錄在前）
                    record_time = base_time - timedelta(hours=random.uniform(0, 24))

                    # 隨機位置（台北市中心附近）
                    lat_offset = random.randint(-20000, 20000)  # ±0.02度
                    lng_offset = random.randint(-20000, 20000)  # ±0.02度

                    # 隨機選擇會員（模擬使用情況）
                    member = (
                        random.choice(list(members))
                        if members.exists() and random.random() > 0.3
                        else None
                    )

                    record = TelemetryRecord(
                        telemetry_device_imei=device.IMEI,
                        bike_id=bike.bike_id,
                        sequence_id=i + 1,
                        # 時間資訊
                        gps_time=record_time,
                        rtc_time=record_time + timedelta(seconds=random.randint(-5, 5)),
                        send_time=record_time
                        + timedelta(seconds=random.randint(0, 10)),
                        # GPS 位置資訊
                        longitude=base_lng + lng_offset,
                        latitude=base_lat + lat_offset,
                        heading_direction=random.randint(0, 359),
                        vehicle_speed=random.randint(0, 30),  # 0-30 km/hr
                        altitude=random.randint(0, 100),  # 0-100公尺
                        gps_hdop=random.randint(10, 50),  # HDOP * 10
                        gps_vdop=random.randint(10, 50),  # VDOP * 10
                        satellites_count=random.randint(4, 12),
                        # 電池與動力資訊
                        battery_voltage=random.randint(360, 420),  # 36-42V * 10
                        soc=random.randint(20, 100),  # 20-100%
                        bike_odometer=random.randint(0, 50000),  # 0-50km (m)
                        assist_level=random.randint(0, 4),
                        pedal_torque=random.randint(0, 5000),  # 扭力 * 100
                        controller_temp=random.randint(20, 60)
                        if random.random() > 0.2
                        else None,
                        pedal_cadence=random.randint(0, 3200),  # 轉速 * 40
                        battery_temp1=random.randint(15, 45)
                        if random.random() > 0.3
                        else None,
                        battery_temp2=random.randint(15, 45)
                        if random.random() > 0.3
                        else None,
                        # 系統狀態資訊
                        acc_status=random.choice([True, False]),
                        output_status=random.randint(0, 3),
                        analog_input=random.randint(0, 5000),  # * 1000
                        backup_battery=random.randint(110, 140),  # 11-14V * 10
                        rssi=random.randint(10, 31),
                        total_odometer=random.randint(0, 100000),  # * 10
                        member_id=str(member.id) if member else '',
                        # 報告資訊
                        report_id=random.randint(1, 5),
                        message=f"Normal operation - Seq {i+1}"
                        if random.random() > 0.1
                        else f"Warning: Low battery - Seq {i+1}",
                        # 同步狀態
                        is_synced=False,  # 新記錄預設為未同步
                    )
                    records.append(record)

            except BikeInfo.DoesNotExist:
                print(f"⚠️ 警告: 找不到對應的車輛 (device_id: {device.IMEI})")
                continue

        if records:
            # 分批創建，避免一次性創建過多記錄
            batch_size = 50
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                TelemetryRecord.objects.bulk_create(batch, ignore_conflicts=True)

            print(f"成功創建 {len(records)} 筆遙測記錄")

            # 統計資訊
            print(f"\n記錄分布:")
            device_counts = {}
            for record in records:
                device_id = record.telemetry_device_imei
                device_counts[device_id] = device_counts.get(device_id, 0) + 1

            for device_id, count in device_counts.items():
                print(f"  - 設備 {device_id}: {count} 筆記錄")

            print(
                f"\n時間範圍: {min(r.gps_time for r in records)} ~ {max(r.gps_time for r in records)}"
            )
        else:
            print('❌ 沒有創建任何記錄')
