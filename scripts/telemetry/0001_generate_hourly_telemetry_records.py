import random
from datetime import datetime, timedelta

from django.utils import timezone

from account.models import Member
from bike.models import BikeInfo
from scripts.base import BaseScript
from telemetry.models import TelemetryDevice, TelemetryRecord


class CustomScript(BaseScript):
    def run(self):
        # 獲取前3個設備和對應的車輛
        devices = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.DEPLOYED
        )[:3]
        members = list(Member.objects.filter(is_active=True))

        if not devices.exists():
            print('⚠️ 警告: 沒有找到遙測設備，請先執行 telemetry devices 腳本')
            return

        if not members:
            print('⚠️ 警告: 沒有找到會員資料，請先建立會員')
            return

        records = []

        # 計算時間範圍（近10天）
        end_time = timezone.now()
        start_time = end_time - timedelta(days=10)

        # 台北市中心的經緯度範圍
        base_lat = 25047000  # 25.047000 * 10^6
        base_lng = 121517000  # 121.517000 * 10^6

        print(f"為 {devices.count()} 個設備創建近10天的遙測資料...")
        print(f"時間範圍: {start_time} ~ {end_time}")
        print(f"資料頻率: 每60秒一筆")

        for device_idx, device in enumerate(devices):
            try:
                bike = BikeInfo.objects.get(telemetry_device=device)
                print(f"\n處理設備 {device.IMEI} (車輛: {bike.bike_id})...")

                # 為每個設備設定不同的基準位置（模擬不同區域）
                device_lat_offset = device_idx * 10000  # 每個設備相隔0.01度
                device_lng_offset = device_idx * 10000
                device_base_lat = base_lat + device_lat_offset
                device_base_lng = base_lng + device_lng_offset

                # 計算總時間差（分鐘）
                total_minutes = int((end_time - start_time).total_seconds() / 60)

                # 每60秒一筆資料
                sequence_id = 1
                current_time = start_time
                device_records = 0

                # 模擬車輛狀態變化
                current_soc = random.randint(80, 100)  # 起始電量
                current_odometer = random.randint(1000, 5000)  # 起始里程表
                total_odometer = random.randint(10000, 50000)  # 總里程表

                while current_time < end_time:
                    # 模擬一天的使用模式（白天較活躍）
                    hour = current_time.hour
                    is_active_period = 6 <= hour <= 22  # 早6點到晚10點較活躍

                    # 活躍期間每分鐘一筆資料，非活躍期間每5分鐘一筆
                    if is_active_period:
                        time_increment = 1  # 1分鐘
                        speed_range = (5, 25)  # 較高速度
                        usage_probability = 0.7  # 70%機率有人使用
                    else:
                        time_increment = 5  # 5分鐘
                        speed_range = (0, 5)  # 較低速度或停止
                        usage_probability = 0.1  # 10%機率有人使用

                    # 模擬位置變化（隨機漫步）
                    if device_records > 0:
                        # 位置微調（模擬移動）
                        lat_change = random.randint(-1000, 1000)  # ±0.001度
                        lng_change = random.randint(-1000, 1000)
                        device_base_lat = max(
                            base_lat - 50000,
                            min(base_lat + 50000, device_base_lat + lat_change),
                        )
                        device_base_lng = max(
                            base_lng - 50000,
                            min(base_lng + 50000, device_base_lng + lng_change),
                        )

                    # 模擬電量消耗
                    if random.random() < 0.1:  # 10%機率電量下降
                        current_soc = max(10, current_soc - random.randint(1, 3))

                    # 模擬里程增加
                    if random.random() < usage_probability:
                        odometer_increase = random.randint(10, 100)  # 10-100公尺
                        current_odometer += odometer_increase
                        total_odometer += odometer_increase

                    # 隨機選擇使用者
                    member = (
                        random.choice(members)
                        if random.random() < usage_probability
                        else None
                    )

                    # 模擬速度
                    vehicle_speed = (
                        random.randint(*speed_range) if member else random.randint(0, 2)
                    )

                    record = TelemetryRecord(
                        telemetry_device_imei=device.IMEI,
                        bike_id=bike.bike_id,
                        sequence_id=sequence_id,
                        # 時間資訊
                        gps_time=current_time,
                        rtc_time=current_time
                        + timedelta(seconds=random.randint(-2, 2)),
                        send_time=current_time
                        + timedelta(seconds=random.randint(0, 5)),
                        # GPS 位置資訊
                        longitude=device_base_lng,
                        latitude=device_base_lat,
                        heading_direction=random.randint(0, 359),
                        vehicle_speed=vehicle_speed,
                        altitude=random.randint(5, 50),
                        gps_hdop=random.randint(10, 30),
                        gps_vdop=random.randint(10, 30),
                        satellites_count=random.randint(6, 12),
                        # 電池與動力資訊
                        battery_voltage=random.randint(360 + current_soc // 3, 420),
                        soc=current_soc,
                        bike_odometer=current_odometer,
                        assist_level=random.randint(0, 4) if member else 0,
                        pedal_torque=random.randint(0, 3000)
                        if member
                        else random.randint(0, 100),
                        controller_temp=random.randint(25, 45)
                        if member
                        else random.randint(20, 30),
                        pedal_cadence=random.randint(0, 2400)
                        if member
                        else random.randint(0, 200),
                        battery_temp1=random.randint(20, 40),
                        battery_temp2=random.randint(20, 40),
                        # 系統狀態資訊
                        acc_status=member is not None,
                        output_status=random.randint(1, 3) if member else 0,
                        analog_input=random.randint(1000, 4000),
                        backup_battery=random.randint(120, 140),
                        rssi=random.randint(15, 31),
                        total_odometer=total_odometer,
                        member_id=str(member.id) if member else '',
                        # 報告資訊
                        report_id=random.randint(1, 5),
                        message=f"Auto-generated data seq {sequence_id}",
                        # 同步狀態
                        is_synced=True,  # 歷史資料設為已同步
                    )
                    # 手動設置 created_at 為遙測時間（稍微延遲幾秒模擬真實情況）
                    record.created_at = current_time + timedelta(
                        seconds=random.randint(1, 10)
                    )
                    records.append(record)

                    sequence_id += 1
                    device_records += 1
                    current_time += timedelta(minutes=time_increment)

                print(f"  設備 {device.IMEI} 準備創建 {device_records} 筆記錄")

            except BikeInfo.DoesNotExist:
                print(f"⚠️ 警告: 找不到對應的車輛 (device_id: {device.IMEI})")
                continue

        if records:
            print(f"\n開始批量創建 {len(records)} 筆遙測記錄...")

            # 分批創建，避免記憶體不足
            batch_size = 1000
            created_count = 0

            from django.db import connection

            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                # 先保存每個記錄的目標 created_at 時間
                created_at_mapping = {}
                for record in batch:
                    key = (
                        record.telemetry_device_imei,
                        record.bike_id,
                        record.sequence_id,
                    )
                    created_at_mapping[key] = record.created_at

                # 批量創建記錄（created_at 會被自動設為當前時間）
                TelemetryRecord.objects.bulk_create(batch, ignore_conflicts=True)

                # 使用 SQL 批量更新 created_at
                with connection.cursor() as cursor:
                    for record in batch:
                        cursor.execute(
                            '''UPDATE telemetry_telemetryrecord
                               SET created_at = %s
                               WHERE telemetry_device_imei = %s
                               AND bike_id = %s
                               AND sequence_id = %s''',
                            [
                                created_at_mapping[
                                    (
                                        record.telemetry_device_imei,
                                        record.bike_id,
                                        record.sequence_id,
                                    )
                                ],
                                record.telemetry_device_imei,
                                record.bike_id,
                                record.sequence_id,
                            ],
                        )

                created_count += len(batch)
                print(
                    f"  已創建並更新 {created_count}/{len(records)} 筆記錄 ({created_count/len(records)*100:.1f}%)"
                )

            print(f"\n✅ 成功創建 {len(records)} 筆遙測記錄")

            # 統計資訊
            print(f"\n📊 記錄分布:")
            device_counts = {}
            for record in records:
                device_id = record.telemetry_device_imei
                device_counts[device_id] = device_counts.get(device_id, 0) + 1

            for device_id, count in device_counts.items():
                print(f"  - 設備 {device_id}: {count:,} 筆記錄")

            print(
                f"\n⏰ 時間範圍: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"
            )
            print(f"📈 平均每小時記錄數: {len(records)/(10*24):.1f}")
        else:
            print('❌ 沒有創建任何記錄')
