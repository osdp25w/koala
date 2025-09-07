import random
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone

from scripts.base import BaseScript
from statistic.models import DailyOverviewStatistics, HourlyOverviewStatistics


class CustomScript(BaseScript):
    def run(self):
        """生成近10天的假統計資料用於測試"""
        print('🚀 開始生成假統計資料...')

        # 設定時間範圍 - 近10天
        end_date = timezone.now().replace(hour=23, minute=59, second=59, microsecond=0)
        start_date = end_date - timedelta(days=9)  # 9天前 + 今天 = 10天

        print(f"📅 時間範圍: {start_date.date()} 到 {end_date.date()}")

        # 1. 生成假的小時統計
        hourly_created = self._generate_fake_hourly_statistics(start_date, end_date)

        # 2. 生成假的每日統計
        daily_created = self._generate_fake_daily_statistics(start_date, end_date)

        print('\n' + '=' * 60)
        print('📈 假資料生成結果:')
        print(f"  🕐 小時統計: {hourly_created} 筆")
        print(f"  📅 每日統計: {daily_created} 筆")
        print('=' * 60)
        print('\n🎉 假資料生成完成!')

    def _generate_fake_hourly_statistics(self, start_date, end_date):
        """生成假的小時統計數據"""
        print(f"\n🔄 生成假的小時統計數據...")

        current_date = start_date
        created_count = 0

        while current_date <= end_date:
            print(f"  📅 處理日期: {current_date.date()}")

            # 為該日期生成24小時的統計
            hourly_objects = []
            for hour in range(24):
                target_datetime = current_date.replace(
                    hour=hour, minute=0, second=0, microsecond=0
                )

                # 檢查是否已存在
                if HourlyOverviewStatistics.objects.filter(
                    collected_time=target_datetime
                ).exists():
                    continue

                # 生成假數據
                online_bikes = random.randint(30, 50)  # 30-50台在線
                offline_bikes = random.randint(5, 15)  # 5-15台離線
                average_soc = round(random.uniform(60.0, 90.0), 1)  # 60-90% SOC
                distance_km = round(random.uniform(2.0, 8.0), 2)  # 每小時2-8公里
                carbon_reduction_kg = round(distance_km * 0.021, 3)  # 每公里21克 = 0.021kg

                hourly_stat = HourlyOverviewStatistics(
                    collected_time=target_datetime,
                    online_bikes_count=online_bikes,
                    offline_bikes_count=offline_bikes,
                    average_soc=average_soc,
                    distance_km=distance_km,
                    carbon_reduction_kg=carbon_reduction_kg,
                )
                hourly_objects.append(hourly_stat)

            # 批量創建
            if hourly_objects:
                HourlyOverviewStatistics.objects.bulk_create(hourly_objects)
                created_count += len(hourly_objects)
                print(f"    ✅ 創建了 {len(hourly_objects)} 筆小時統計")

            current_date += timedelta(days=1)

        print(f"  📊 小時統計完成: {created_count} 筆")
        return created_count

    def _generate_fake_daily_statistics(self, start_date, end_date):
        """生成假的每日統計數據"""
        print(f"\n🔄 生成假的每日統計數據...")

        current_date = start_date.date()
        end_date = end_date.date()
        created_count = 0

        daily_objects = []
        while current_date <= end_date:
            # 檢查是否已存在
            if DailyOverviewStatistics.objects.filter(
                collected_time=current_date
            ).exists():
                current_date += timedelta(days=1)
                continue

            # 從該日期的小時統計計算聚合值
            hourly_stats = HourlyOverviewStatistics.objects.filter(
                collected_time__date=current_date
            )

            if hourly_stats.exists():
                # 從小時統計聚合數據
                online_bikes = round(
                    hourly_stats.aggregate(avg=models.Avg('online_bikes_count'))['avg']
                    or 0
                )
                offline_bikes = round(
                    hourly_stats.aggregate(avg=models.Avg('offline_bikes_count'))['avg']
                    or 0
                )
                daily_distance = (
                    hourly_stats.aggregate(total=models.Sum('distance_km'))['total']
                    or 0.0
                )
                carbon_reduction = (
                    hourly_stats.aggregate(total=models.Sum('carbon_reduction_kg'))[
                        'total'
                    ]
                    or 0.0
                )
                average_soc = hourly_stats.aggregate(avg=models.Avg('average_soc'))[
                    'avg'
                ]
            else:
                # 如果沒有小時統計，生成假數據
                online_bikes = random.randint(35, 45)
                offline_bikes = random.randint(8, 12)
                daily_distance = round(random.uniform(50.0, 150.0), 2)
                carbon_reduction = round(daily_distance * 0.021, 3)  # 使用新的係數
                average_soc = round(random.uniform(65.0, 85.0), 1)

            daily_stat = DailyOverviewStatistics(
                collected_time=current_date,
                online_bikes_count=online_bikes,
                offline_bikes_count=offline_bikes,
                total_distance_km=round(daily_distance, 2),
                carbon_reduction_kg=round(carbon_reduction, 3),
                average_soc=average_soc,
            )
            daily_objects.append(daily_stat)

            current_date += timedelta(days=1)

        # 批量創建
        if daily_objects:
            DailyOverviewStatistics.objects.bulk_create(daily_objects)
            created_count = len(daily_objects)

            print('  ✅ 創建的每日統計:')
            for daily_stat in daily_objects:
                print(
                    f"    📅 {daily_stat.collected_time}: 在線 {daily_stat.online_bikes_count}, "
                    f"里程 {daily_stat.total_distance_km}km, 減碳 {daily_stat.carbon_reduction_kg}kg, "
                    f"SOC {daily_stat.average_soc}%"
                )

        print(f"  📊 每日統計完成: {created_count} 筆")
        return created_count
