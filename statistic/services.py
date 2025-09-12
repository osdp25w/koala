import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from django.db.models import Avg, Max, Sum
from django.utils import timezone

from bike.models import BikeInfo, BikeRealtimeStatus
from statistic.models import DailyOverviewStatistics, HourlyOverviewStatistics
from telemetry.models import TelemetryRecord

logger = logging.getLogger(__name__)


class HourlyStatisticsService:
    @staticmethod
    def calculate_bike_status_counts() -> Dict[str, int]:
        """計算車輛在線/離線狀態統計"""
        try:
            online_count = BikeRealtimeStatus.objects.filter(
                status__in=BikeRealtimeStatus.STATUS_ONLINE, bike__is_active=True
            ).count()

            offline_count = BikeRealtimeStatus.objects.filter(
                status__in=BikeRealtimeStatus.STATUS_OFFLINE, bike__is_active=True
            ).count()

            return {
                'online_bikes_count': online_count,
                'offline_bikes_count': offline_count,
            }

        except Exception as e:
            logger.error(f"Error calculating bike status counts: {e}")
            return {'online_bikes_count': 0, 'offline_bikes_count': 0}

    @staticmethod
    def calculate_hourly_average_soc(target_datetime: datetime) -> Optional[float]:
        """計算指定小時的平均SOC"""
        try:
            avg_soc = TelemetryRecord.objects.filter(
                created_at__date=target_datetime.date(),
                created_at__hour=target_datetime.hour,
                soc__isnull=False,
            ).aggregate(avg_soc=Avg('soc'))['avg_soc']

            return avg_soc

        except Exception as e:
            logger.error(
                f"Error calculating hourly average SOC for {target_datetime}: {e}"
            )
            return None

    @staticmethod
    def calculate_hourly_distance_increment(target_datetime: datetime) -> float:
        """計算指定小時的新增里程"""
        try:
            # 計算該小時內所有車輛的總里程
            current_hour_odometers = (
                TelemetryRecord.objects.filter(
                    created_at__date=target_datetime.date(),
                    created_at__hour=target_datetime.hour,
                )
                .values('bike_id')
                .annotate(max_total_odometer=Max('total_odometer'))
                .aggregate(total_sum=Sum('max_total_odometer'))
            )

            current_hour_total = (
                current_hour_odometers['total_sum'] or 0
            ) / 10.0  # 0.1km -> km

            # 計算前一小時的總里程
            prev_datetime = target_datetime - timedelta(hours=1)
            prev_hour_odometers = (
                TelemetryRecord.objects.filter(
                    created_at__date=prev_datetime.date(),
                    created_at__hour=prev_datetime.hour,
                )
                .values('bike_id')
                .annotate(max_total_odometer=Max('total_odometer'))
                .aggregate(total_sum=Sum('max_total_odometer'))
            )

            prev_hour_total = (
                prev_hour_odometers['total_sum'] or 0
            ) / 10.0  # 0.1km -> km

            # 計算該小時新增里程
            hourly_increment = max(0, current_hour_total - prev_hour_total)

            logger.debug(
                f"Hourly distance for {target_datetime}: "
                f"Current: {current_hour_total:.2f}km, Previous: {prev_hour_total:.2f}km, "
                f"Increment: {hourly_increment:.2f}km"
            )

            return hourly_increment

        except Exception as e:
            logger.error(
                f"Error calculating hourly distance for {target_datetime}: {e}"
            )
            return 0.0

    @staticmethod
    def calculate_hourly_carbon_reduction(distance_km: float) -> float:
        """計算小時減碳效益"""
        # 每公里21克 CO₂ = 0.021 kg CO₂
        CARBON_REDUCTION_RATE = 0.021
        return distance_km * CARBON_REDUCTION_RATE

    @classmethod
    def collect_hourly_statistics(cls, target_datetime: datetime) -> Dict:
        """創建小時統計記錄"""
        try:
            # 計算各項統計
            bike_counts = cls.calculate_bike_status_counts()
            avg_soc = cls.calculate_hourly_average_soc(target_datetime)
            hourly_distance = cls.calculate_hourly_distance_increment(target_datetime)
            hourly_carbon = cls.calculate_hourly_carbon_reduction(hourly_distance)

            # 創建或更新記錄
            hourly_stats, created = HourlyOverviewStatistics.objects.update_or_create(
                collected_time=target_datetime,
                defaults={
                    **bike_counts,
                    'average_soc': avg_soc,
                    'distance_km': hourly_distance,
                    'carbon_reduction_kg': hourly_carbon,
                },
            )

            result = {
                'success': True,
                'collected_time': target_datetime.isoformat(),
                'action': 'created' if created else 'updated',
                **bike_counts,
                'average_soc': avg_soc,
                'distance_km': hourly_distance,
                'carbon_reduction_kg': hourly_carbon,
            }

            logger.info(
                f"{'Created' if created else 'Updated'} hourly statistics for {target_datetime}"
            )
            return result

        except Exception as e:
            logger.error(f"Error creating hourly statistics for {target_datetime}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def calculate_realtime_hourly_statistics(cls, target_datetime: datetime) -> Dict:
        """即時計算小時統計（不存DB）"""
        try:
            # 計算各項統計
            bike_counts = cls.calculate_bike_status_counts()
            avg_soc = cls.calculate_hourly_average_soc(target_datetime)
            hourly_distance = cls.calculate_hourly_distance_increment(target_datetime)
            hourly_carbon = cls.calculate_hourly_carbon_reduction(hourly_distance)

            return {
                'collected_time': target_datetime,
                'online_bikes_count': bike_counts['online_bikes_count'],
                'offline_bikes_count': bike_counts['offline_bikes_count'],
                'average_soc': avg_soc,
                'distance_km': hourly_distance,
                'carbon_reduction_kg': hourly_carbon,
            }

        except Exception as e:
            logger.error(
                f"Error calculating realtime hourly statistics for {target_datetime}: {e}"
            )
            return None


class DailyStatisticsService:
    @staticmethod
    def aggregate_bike_status_from_hourly(date) -> Dict[str, int]:
        """從小時統計聚合車輛狀態數據"""
        try:
            hourly_stats = HourlyOverviewStatistics.objects.filter(
                collected_time__date=date
            )

            if not hourly_stats.exists():
                logger.warning(f"No hourly statistics found for {date}")
                return {'online_bikes_count': 0, 'offline_bikes_count': 0}

            online_avg = (
                hourly_stats.aggregate(avg=Avg('online_bikes_count'))['avg'] or 0
            )
            offline_avg = (
                hourly_stats.aggregate(avg=Avg('offline_bikes_count'))['avg'] or 0
            )

            return {
                'online_bikes_count': round(online_avg),
                'offline_bikes_count': round(offline_avg),
            }

        except Exception as e:
            logger.error(f"Error aggregating bike status for {date}: {e}")
            return {'online_bikes_count': 0, 'offline_bikes_count': 0}

    @staticmethod
    def aggregate_soc_from_hourly(date) -> Optional[float]:
        """從小時統計聚合平均SOC"""
        try:
            hourly_stats = HourlyOverviewStatistics.objects.filter(
                collected_time__date=date
            )
            soc_avg = hourly_stats.aggregate(avg=Avg('average_soc'))['avg']

            return soc_avg

        except Exception as e:
            logger.error(f"Error aggregating SOC for {date}: {e}")
            return None

    @staticmethod
    def aggregate_distance_from_hourly(date) -> float:
        """從小時統計聚合每日總里程"""
        try:
            hourly_stats = HourlyOverviewStatistics.objects.filter(
                collected_time__date=date
            )

            if not hourly_stats.exists():
                logger.warning(f"No hourly statistics found for {date}")
                return 0.0

            total_distance = (
                hourly_stats.aggregate(total=Sum('distance_km'))['total'] or 0.0
            )

            logger.info(
                f"Daily distance aggregated for {date}: {total_distance:.2f}km from {hourly_stats.count()} hourly records"
            )
            return total_distance

        except Exception as e:
            logger.error(f"Error aggregating distance for {date}: {e}")
            return 0.0

    @staticmethod
    def aggregate_carbon_from_hourly(date) -> float:
        """從小時統計聚合每日減碳效益"""
        try:
            hourly_stats = HourlyOverviewStatistics.objects.filter(
                collected_time__date=date
            )

            if not hourly_stats.exists():
                logger.warning(f"No hourly statistics found for {date}")
                return 0.0

            total_carbon = (
                hourly_stats.aggregate(total=Sum('carbon_reduction_kg'))['total'] or 0.0
            )

            logger.info(
                f"Daily carbon reduction aggregated for {date}: {total_carbon:.3f}kg from {hourly_stats.count()} hourly records"
            )
            return total_carbon

        except Exception as e:
            logger.error(f"Error aggregating carbon reduction for {date}: {e}")
            return 0.0

    @classmethod
    def collect_daily_statistics(cls, date) -> Dict:
        """創建每日統計記錄"""
        try:
            logger.info(f"Starting daily statistics calculation for {date}")

            # 1. 聚合車輛狀態數據
            bike_counts = cls.aggregate_bike_status_from_hourly(date)

            # 2. 聚合SOC數據
            avg_soc = cls.aggregate_soc_from_hourly(date)

            # 3. 聚合里程數據
            daily_distance = cls.aggregate_distance_from_hourly(date)

            # 4. 聚合減碳效益
            carbon_reduction = cls.aggregate_carbon_from_hourly(date)

            # 6. 創建或更新記錄
            daily_stats, created = DailyOverviewStatistics.objects.update_or_create(
                collected_time=date,
                defaults={
                    **bike_counts,
                    'total_distance_km': daily_distance,
                    'carbon_reduction_kg': carbon_reduction,
                    'average_soc': avg_soc,
                },
            )

            result = {
                'success': True,
                'collected_time': date.isoformat(),
                'action': 'created' if created else 'updated',
                **bike_counts,
                'total_distance_km': daily_distance,
                'carbon_reduction_kg': carbon_reduction,
                'average_soc': avg_soc,
            }

            logger.info(
                f"{'Created' if created else 'Updated'} daily statistics for {date}"
            )
            return result

        except Exception as e:
            logger.error(f"Error creating daily statistics for {date}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def calculate_realtime_daily_statistics(cls, date) -> Dict:
        """即時計算日統計（不存DB），從已有的小時統計聚合"""
        try:
            # 聚合已有的小時統計
            bike_counts = cls.aggregate_bike_status_from_hourly(date)
            avg_soc = cls.aggregate_soc_from_hourly(date)
            daily_distance = cls.aggregate_distance_from_hourly(date)
            carbon_reduction = cls.aggregate_carbon_from_hourly(date)

            return {
                'collected_time': date,
                'online_bikes_count': bike_counts['online_bikes_count'],
                'offline_bikes_count': bike_counts['offline_bikes_count'],
                'total_distance_km': daily_distance,
                'carbon_reduction_kg': carbon_reduction,
                'average_soc': avg_soc,
            }

        except Exception as e:
            logger.error(f"Error calculating realtime daily statistics for {date}: {e}")
            return None
