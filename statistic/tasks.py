import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from rental.models import BikeRental
from statistic.models import HourlyOverviewStatistics, RideSession, RouteMatchResult
from statistic.services import (
    DailyStatisticsService,
    GeometryCoordinateService,
    HourlyStatisticsService,
    RouteAnalysisService,
    TrajectoryExtractionService,
)

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


@shared_task(bind=True, max_retries=3, default_retry_delay=15, queue='statistics_q')
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
        result = HourlyStatisticsService.collect_hourly_statistics(target_datetime)

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue='statistics_q')
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
        result = DailyStatisticsService.collect_daily_statistics(date)

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue='statistics_q')
def extract_ride_trajectory(self, bike_rental_id: int):
    """提取騎乘軌跡任務"""
    try:
        logger.info(f"Starting trajectory extraction for BikeRental {bike_rental_id}")

        bike_rental = BikeRental.objects.get(id=bike_rental_id)
        ride_session = bike_rental.ride_session

        ride_session.status = RideSession.StatusOptions.EXTRACTING
        ride_session.save()

        result = TrajectoryExtractionService.extract_gps_trajectory(bike_rental)

        if result['success']:
            logger.info(
                f"Successfully extracted trajectory: {result['valid_points']} valid points from {result['total_raw_points']} raw points"
            )
            analyze_route.delay(result['ride_session_id'])
        else:
            logger.error(f"Failed to extract trajectory: {result['error']}")
            ride_session.status = RideSession.StatusOptions.FAILED
            ride_session.error_message = result['error']
            ride_session.save()

        return result

    except Exception as e:
        logger.error(
            f"Error extracting trajectory for BikeRental {bike_rental_id}: {e}"
        )
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60, queue='statistics_q')
def analyze_route(self, ride_session_id: int):
    """分析路線段任務"""
    try:
        logger.info(f"Starting route analysis for RideSession {ride_session_id}")

        ride_session = RideSession.objects.get(id=ride_session_id)
        ride_session.status = RideSession.StatusOptions.ANALYZING
        ride_session.save()

        result = RouteAnalysisService.analyze_ride_route(ride_session_id)

        if result['success']:
            logger.info(
                f"Successfully analyzed route for RideSession {ride_session_id}"
            )
            ride_session.status = RideSession.StatusOptions.COMPLETED
            ride_session.save()
        else:
            logger.error(f"Failed to analyze route: {result['error']}")
            ride_session.status = RideSession.StatusOptions.FAILED
            ride_session.error_message = result['error']
            ride_session.save()

        return result

    except Exception as e:
        logger.error(f"Error analyzing route for RideSession {ride_session_id}: {e}")
        raise


@shared_task(
    bind=True, max_retries=3, default_retry_delay=300, queue='statistics_q'
)  # 5分鐘重試間隔
def retry_failed_coordinate_sync(self):
    """重新處理座標統計失敗的 RouteMatchResult"""

    try:
        # 查找所有未同步座標統計的 RouteMatchResult
        failed_results = RouteMatchResult.objects.filter(
            is_sync_geometry_coordinate=False, resync_details__isnull=False  # 只處理有重試資訊的
        ).order_by('created_at')

        if not failed_results.exists():
            logger.info(
                'No failed coordinate sync with resync details found, task completed'
            )
            return {'processed': 0, 'success': 0, 'failed': 0}

        logger.info(
            f"Found {failed_results.count()} RouteMatchResult(s) with failed coordinate sync"
        )

        processed = 0
        success_count = 0
        failed_count = 0

        for result in failed_results:
            try:
                processed += 1
                logger.info(
                    f"Retrying coordinate sync for RouteMatchResult {result.id}"
                )

                # 從 resync_details 取得原始的 marked_coordinates
                resync_data = result.resync_details
                if not resync_data or 'marked_coordinates' not in resync_data:
                    logger.warning(
                        f"RouteMatchResult {result.id} has invalid resync_details, skipping"
                    )
                    failed_count += 1
                    continue

                marked_coordinates = resync_data['marked_coordinates']
                ride_end_time_str = resync_data.get('ride_end_time')

                # 解析騎乘結束時間
                ride_end_time = None
                if ride_end_time_str:
                    try:
                        ride_end_time = datetime.fromisoformat(
                            ride_end_time_str.replace('Z', '+00:00')
                        )
                    except:
                        ride_end_time = result.ride_session.bike_rental.end_time

                # 重新處理座標統計
                GeometryCoordinateService.process_and_deduplicate_coordinates(
                    marked_coordinates, ride_end_time
                )

                # 標記為已完成，清除重試資訊
                result.is_sync_geometry_coordinate = True
                result.resync_details = None
                result.save(
                    update_fields=['is_sync_geometry_coordinate', 'resync_details']
                )

                success_count += 1
                logger.info(
                    f"Successfully retried coordinate sync for RouteMatchResult {result.id}"
                )

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to retry coordinate sync for RouteMatchResult {result.id}: {e}"
                )

                # 更新錯誤資訊
                if result.resync_details:
                    result.resync_details['last_retry_error'] = str(e)
                    result.resync_details['last_retry_at'] = timezone.now().isoformat()
                    result.save(update_fields=['resync_details'])
                continue

        logger.info(
            f"Coordinate sync retry completed: {processed} processed, {success_count} success, {failed_count} failed"
        )

        return {
            'processed': processed,
            'success': success_count,
            'failed': failed_count,
        }

    except Exception as e:
        logger.error(f"Error in retry_failed_coordinate_sync task: {e}")
        raise
