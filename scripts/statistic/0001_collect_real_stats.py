from datetime import datetime, timedelta

from django.utils import timezone

from scripts.base import BaseScript
from statistic.models import DailyOverviewStatistics, HourlyOverviewStatistics
from statistic.services import DailyStatisticsService, HourlyStatisticsService


class CustomScript(BaseScript):
    def run(self):
        """生成近10天的小時和每日統計資料"""
        print('🚀 開始生成歷史統計資料...')

        # 設定時間範圍 - 近10天
        end_date = timezone.now().replace(hour=23, minute=59, second=59, microsecond=0)
        start_date = end_date - timedelta(days=9)  # 9天前 + 今天 = 10天

        print(f"📅 時間範圍: {start_date.date()} 到 {end_date.date()}")

        # 1. 生成小時統計
        hourly_success, hourly_total = self._generate_hourly_statistics(
            start_date, end_date
        )

        # 2. 生成每日統計
        daily_success, daily_total = self._generate_daily_statistics(
            start_date, end_date
        )

        # 3. 統計結果
        print('\n' + '=' * 60)
        print('📈 統計結果總覽:')
        print(
            f"  🕐 小時統計: {hourly_success}/{hourly_total} 成功 ({hourly_success/hourly_total*100:.1f}%)"
        )
        print(
            f"  📅 每日統計: {daily_success}/{daily_total} 成功 ({daily_success/daily_total*100:.1f}%)"
        )
        print('=' * 60)

        # 4. 驗證生成的數據
        self._validate_generated_data(start_date, end_date)

        print('\n🎉 腳本執行完成!')

    def _generate_hourly_statistics(self, start_date, end_date):
        """生成小時統計數據"""
        print(f"\n🔄 生成小時統計數據...")

        current_date = start_date
        total_hours = 0
        success_hours = 0

        while current_date <= end_date:
            print(f"  📅 處理日期: {current_date.date()}")

            # 為該日期生成24小時的統計
            for hour in range(24):
                target_datetime = current_date.replace(
                    hour=hour, minute=0, second=0, microsecond=0
                )

                # 檢查是否已存在
                if HourlyOverviewStatistics.objects.filter(
                    collected_time=target_datetime
                ).exists():
                    print(
                        f"    ⏭️  跳過 {target_datetime.strftime('%Y-%m-%d %H:00')} (已存在)"
                    )
                    continue

                try:
                    # 生成統計
                    result = HourlyStatisticsService.collect_hourly_statistics(
                        target_datetime
                    )

                    if result['success']:
                        success_hours += 1
                        soc_str = (
                            f"{result['average_soc']:.1f}"
                            if result['average_soc']
                            else 'N/A'
                        )
                        print(
                            f"    ✅ {target_datetime.strftime('%Y-%m-%d %H:00')}: 在線 {result['online_bikes_count']}, "
                            f"里程 {result['distance_km']:.2f}km, 減碳 {result['carbon_reduction_kg']:.3f}kg, SOC {soc_str}%"
                        )
                    else:
                        print(
                            f"    ❌ {target_datetime.strftime('%Y-%m-%d %H:00')}: {result.get('error', 'Unknown error')}"
                        )

                except Exception as e:
                    print(
                        f"    💥 {target_datetime.strftime('%Y-%m-%d %H:00')}: Exception - {e}"
                    )

                total_hours += 1

            current_date += timedelta(days=1)

        print(f"  📊 小時統計完成: {success_hours}/{total_hours} 成功")
        return success_hours, total_hours

    def _generate_daily_statistics(self, start_date, end_date):
        """生成每日統計數據"""
        print(f"\n🔄 生成每日統計數據...")

        current_date = start_date.date()
        end_date = end_date.date()
        total_days = 0
        success_days = 0

        while current_date <= end_date:
            # 檢查是否已存在
            if DailyOverviewStatistics.objects.filter(
                collected_time=current_date
            ).exists():
                print(f"  ⏭️  跳過 {current_date} (已存在)")
                current_date += timedelta(days=1)
                continue

            try:
                # 生成統計
                result = DailyStatisticsService.collect_daily_statistics(current_date)

                if result['success']:
                    success_days += 1
                    soc_str = (
                        f"{result['average_soc']:.1f}"
                        if result['average_soc']
                        else 'N/A'
                    )
                    print(
                        f"  ✅ {current_date}: 在線 {result['online_bikes_count']}, 里程 {result['total_distance_km']:.2f}km, 減碳 {result['carbon_reduction_kg']:.2f}kg, SOC {soc_str}%"
                    )
                else:
                    print(f"  ❌ {current_date}: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"  💥 {current_date}: Exception - {e}")

            total_days += 1
            current_date += timedelta(days=1)

        print(f"  📊 每日統計完成: {success_days}/{total_days} 成功")
        return success_days, total_days

    def _validate_generated_data(self, start_date, end_date):
        """驗證生成的數據"""
        print('\n🔍 驗證生成的數據:')

        hourly_count = HourlyOverviewStatistics.objects.filter(
            collected_time__gte=start_date, collected_time__lte=end_date
        ).count()

        daily_count = DailyOverviewStatistics.objects.filter(
            collected_time__gte=start_date.date(), collected_time__lte=end_date.date()
        ).count()

        print(f"  📊 資料庫中小時記錄數: {hourly_count}")
        print(f"  📊 資料庫中每日記錄數: {daily_count}")

        # 簡單的資料完整性檢查
        expected_days = (end_date.date() - start_date.date()).days + 1
        print(f"  🎯 預期天數: {expected_days}")

        if daily_count > 0:
            latest_daily = (
                DailyOverviewStatistics.objects.filter(
                    collected_time__gte=start_date.date(),
                    collected_time__lte=end_date.date(),
                )
                .order_by('-collected_time')
                .first()
            )

            print(
                f"  📅 最新每日統計: {latest_daily.collected_time} (在線: {latest_daily.online_bikes_count}, "
                f"里程: {latest_daily.total_distance_km:.2f}km, 減碳: {latest_daily.carbon_reduction_kg:.3f}kg)"
            )

        if hourly_count > 0:
            latest_hourly = (
                HourlyOverviewStatistics.objects.filter(
                    collected_time__gte=start_date, collected_time__lte=end_date
                )
                .order_by('-collected_time')
                .first()
            )

            soc_str = (
                f"{latest_hourly.average_soc:.1f}"
                if latest_hourly.average_soc
                else 'N/A'
            )
            print(
                f"  🕐 最新小時統計: {latest_hourly.collected_time} (在線: {latest_hourly.online_bikes_count}, "
                f"里程: {latest_hourly.distance_km:.2f}km, 減碳: {latest_hourly.carbon_reduction_kg:.3f}kg, SOC: {soc_str}%)"
            )
