import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from statistic.models import HourlyOverviewStatistics
from statistic.services import DailyStatisticsService, HourlyStatisticsService
from utils.decorators import celery_retry

logger = logging.getLogger(__name__)


@shared_task(queue='statistics_q')
def trigger_hourly_statistics():
    """
    小時統計觸發器
    每小時執行，計算前一小時的時間並觸發統計任務
    """
    # 計算前一小時
    now = timezone.now()
    previous_hour = (now - timedelta(hours=1)).replace(
        minute=0, second=0, microsecond=0
    )
    target_hour_iso = previous_hour.isoformat()

    logger.info(f"Triggering hourly statistics for {target_hour_iso}")

    # 觸發真正的統計任務
    calculate_hourly_statistics.delay(target_hour_iso)

    return f"Triggered hourly statistics for {target_hour_iso}"


@shared_task(queue='statistics_q')
def trigger_daily_statistics():
    """
    每日統計觸發器
    每日執行，計算前一天的日期並觸發統計任務
    """
    # 計算前一天
    yesterday = (timezone.now() - timedelta(days=1)).date()
    target_date_str = yesterday.strftime('%Y-%m-%d')

    logger.info(f"Triggering daily statistics for {target_date_str}")

    # 觸發真正的統計任務
    calculate_daily_statistics.delay(target_date_str)

    return f"Triggered daily statistics for {target_date_str}"


@shared_task(bind=True, queue='statistics_q')
@celery_retry(max_retries=3, countdown=15)  # 3次重試，間隔15秒
def calculate_hourly_statistics(self, target_hour: str = None):
    """
    每小時統計任務
    計算車輛在線狀態和平均SOC

    Args:
        target_hour: 目標小時 (ISO format), 預設為當前小時

    Example:
        # 統計 2025-09-07 14:00 的數據
        calculate_hourly_statistics.delay("2025-09-07T14:00:00")

        # 統計當前小時
        calculate_hourly_statistics.delay()
    """
    try:
        if target_hour:
            target_datetime = datetime.fromisoformat(target_hour)
        else:
            now = timezone.now()
            target_datetime = now.replace(minute=0, second=0, microsecond=0)

        logger.info(f"Starting hourly statistics calculation for {target_datetime}")

        # 調用服務層處理業務邏輯
        result = HourlyStatisticsService.create_hourly_statistics(target_datetime)

        if result['success']:
            logger.info(
                f"{result['action'].title()} hourly statistics for {target_datetime}: "
                f"Online: {result['online_bikes_count']}, "
                f"Offline: {result['offline_bikes_count']}, "
                f"Distance: {result['distance_km']:.2f}km, "
                f"Carbon: {result['carbon_reduction_kg']:.3f}kg, "
                f"Avg SOC: {result['average_soc']}%"
            )

        return result

    except Exception as e:
        logger.error(f"Error in hourly statistics task for {target_hour}: {e}")
        raise


@shared_task(bind=True, queue='statistics_q')
@celery_retry(max_retries=3, countdown=60)
def calculate_daily_statistics(self, target_date: str = None):
    """
    每日統計任務
    從小時統計聚合數據並計算當日新增里程

    Args:
        target_date: 目標日期 (YYYY-MM-DD), 預設為當天

    Example:
        # 統計 2025-09-07 的數據
        calculate_daily_statistics.delay("2025-09-07")

        # 統計當天數據
        calculate_daily_statistics.delay()
    """
    try:
        if target_date:
            date = datetime.strptime(target_date, '%Y-%m-%d').date()
        else:
            # 預設統計當天的數據
            date = timezone.now().date()

        logger.info(f"Starting daily statistics calculation for {date}")

        # 檢查小時統計是否完整
        expected_hours = 24
        actual_hours = HourlyOverviewStatistics.objects.filter(
            collected_time__date=date
        ).count()

        if actual_hours < expected_hours:
            error_msg = f"Incomplete hourly data for {date}: {actual_hours}/{expected_hours} hours available"
            logger.warning(error_msg)
            raise Exception(error_msg)  # 拋出異常觸發重試

        # 調用服務層處理業務邏輯
        result = DailyStatisticsService.create_daily_statistics(date)

        if result['success']:
            logger.info(
                f"{result['action'].title()} daily statistics for {date}: "
                f"Avg Online: {result['online_bikes_count']}, "
                f"Distance: {result['total_distance_km']}km, "
                f"Carbon: {result['carbon_reduction_kg']}kg, "
                f"Avg SOC: {result['average_soc']}%"
            )

        return result

    except Exception as e:
        logger.error(f"Error in daily statistics task for {target_date}: {e}")
        raise
