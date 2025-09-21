import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import Distance
from django.db import models
from django.db.models import Avg, F, Max, Sum
from django.utils import timezone

from bike.models import BikeInfo, BikeRealtimeStatus
from bike.services import BikeErrorLogService
from rental.models import BikeRental
from statistic.models import (
    DailyGeometryCoordinateStatistics,
    DailyOverviewStatistics,
    GeometryCoordinate,
    HourlyGeometryCoordinateStatistics,
    HourlyOverviewStatistics,
    RideSession,
    RouteMatchResult,
)
from telemetry.models import TelemetryRecord
from utils.coordinate import CoordinateDistanceCalculator

logger = logging.getLogger(__name__)


class HourlyStatisticsService:
    @staticmethod
    def calculate_bike_status_counts() -> Dict[str, int]:
        """計算車輛在線/離線狀態統計"""
        try:
            online_count = BikeRealtimeStatus.objects.filter(
                status__in=BikeRealtimeStatus.STATUS_ONLINE
            ).count()

            offline_count = BikeRealtimeStatus.objects.filter(
                status__in=BikeRealtimeStatus.STATUS_OFFLINE
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


class GPSPointValidator:
    """GPS點驗證器 - 統一處理所有GPS點的驗證邏輯"""

    MIN_DISTANCE_M = 10
    MAX_SPEED_KMH = 30

    @staticmethod
    def is_valid_point(record: Dict, valid_gps_points: List[Dict]) -> tuple[bool, str]:
        """檢查GPS點是否有效

        Returns:
            tuple: (是否有效, 失敗原因)
        """
        # 1. 檢查座標是否有效
        if not GPSPointValidator._is_valid_coordinate(record):
            return False, 'Invalid coordinates (0,0)'

        # 2. 檢查GPS信號品質
        if not GPSPointValidator._is_good_signal_quality(record):
            return False, 'Poor GPS signal quality (RSSI=99)'

        lat_decimal = record['latitude'] / 1000000.0
        lng_decimal = record['longitude'] / 1000000.0

        # 3. 檢查座標是否在台灣範圍內
        if not GPSPointValidator._is_in_taiwan_bounds(lat_decimal, lng_decimal):
            return False, 'Coordinates outside Taiwan bounds'

        # 4. 檢查與前一個點的距離
        if valid_gps_points:
            current_point = {
                'lat': lat_decimal,
                'lng': lng_decimal,
                'time': record['gps_time'].isoformat(),
            }

            # 檢查距離是否過近
            if GPSPointValidator._is_distance_too_close(
                current_point, valid_gps_points
            ):
                return (
                    False,
                    f"Distance too close (< {GPSPointValidator.MIN_DISTANCE_M}m)",
                )

            # 檢查移動速度是否過快
            if GPSPointValidator._is_speed_too_fast(
                current_point, valid_gps_points, record['gps_time']
            ):
                return False, 'Speed too fast'

        return True, ''

    @staticmethod
    def _is_valid_coordinate(record: Dict) -> bool:
        """檢查座標是否有效"""
        return record['latitude'] != 0 and record['longitude'] != 0

    @staticmethod
    def _is_good_signal_quality(record: Dict) -> bool:
        """檢查GPS信號品質"""
        return not (record.get('rssi') == 99)

    @staticmethod
    def _is_in_taiwan_bounds(lat_decimal: float, lng_decimal: float) -> bool:
        """檢查座標是否在台灣範圍內"""
        return 21.0 <= lat_decimal <= 26.0 and 119.0 <= lng_decimal <= 123.0

    @staticmethod
    def _is_distance_too_close(
        current_point: Dict, valid_gps_points: List[Dict]
    ) -> bool:
        """檢查與前一個點的距離是否太近"""
        last_point = valid_gps_points[-1]
        distance_m = GPSPointValidator._calculate_distance(current_point, last_point)
        return distance_m < GPSPointValidator.MIN_DISTANCE_M

    @staticmethod
    def _is_speed_too_fast(
        current_point: Dict, valid_gps_points: List[Dict], current_time
    ) -> bool:
        """檢查與前一個點的移動速度是否過快"""
        last_point = valid_gps_points[-1]
        last_time = datetime.fromisoformat(last_point['time'].replace('Z', '+00:00'))
        time_diff = abs((current_time - last_time).total_seconds())

        distance_m = GPSPointValidator._calculate_distance(current_point, last_point)
        speed_ms = distance_m / time_diff
        speed_kmh = speed_ms * 3.6

        return speed_kmh > GPSPointValidator.MAX_SPEED_KMH

    @staticmethod
    def _calculate_distance(point1: Dict, point2: Dict) -> float:
        """計算兩點間距離（米）"""
        gis_point1 = Point(point1['lng'], point1['lat'], srid=4326)
        gis_point2 = Point(point2['lng'], point2['lat'], srid=4326)

        point1_projected = gis_point1.transform(3857, clone=True)
        point2_projected = gis_point2.transform(3857, clone=True)

        return point1_projected.distance(point2_projected)


class TrajectoryExtractionService:
    """軌跡提取服務 - 基本過濾後交給OSRM處理"""

    @staticmethod
    def extract_gps_trajectory(bike_rental: BikeRental) -> Dict:
        """從BikeRental提取GPS軌跡，只做基本過濾"""
        try:
            logger.info(f"Extracting GPS trajectory for rental {bike_rental.id}")

            gps_records = (
                TelemetryRecord.objects.filter(
                    bike_id=bike_rental.bike.bike_id,
                    gps_time__gte=bike_rental.start_time,
                    gps_time__lte=bike_rental.end_time,
                )
                .values('latitude', 'longitude', 'gps_time', 'rssi')
                .order_by('gps_time')
            )
            total_raw_points = gps_records.count()

            logger.info(
                f"Found {total_raw_points} raw GPS points for rental {bike_rental.id}"
            )

            if total_raw_points == 0:
                return {
                    'success': False,
                    'error': 'No GPS points found for this rental period',
                }

            # 使用GPS點過濾器
            valid_gps_points = TrajectoryExtractionService._filter_gps_points(
                gps_records
            )

            if not valid_gps_points:
                return {
                    'success': False,
                    'error': 'No valid GPS points after basic filtering',
                }

            # 3. 更新RideSession
            ride_session = bike_rental.ride_session
            ride_session.raw_point_count = total_raw_points
            ride_session.valid_point_count = len(valid_gps_points)
            ride_session.gps_trajectory = valid_gps_points
            ride_session.save()

            logger.info(
                f"Successfully extracted trajectory for rental {bike_rental.id}: "
                f"{total_raw_points} raw -> {len(valid_gps_points)} valid points"
            )

            return {
                'success': True,
                'ride_session_id': bike_rental.ride_session.id,
                'total_raw_points': total_raw_points,
                'valid_points': len(valid_gps_points),
                'filtered_out': total_raw_points - len(valid_gps_points),
            }

        except Exception as e:
            logger.error(
                f"Error extracting GPS trajectory for rental {bike_rental.id}: {e}"
            )
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _filter_gps_points(gps_records) -> List[Dict]:
        """過濾GPS點"""
        valid_gps_points = []
        filtered_count = 0

        for record in gps_records:
            is_valid, reason = GPSPointValidator.is_valid_point(
                record, valid_gps_points
            )

            if not is_valid:
                filtered_count += 1
                logger.debug(f"Filtered GPS point: {reason}")
                continue

            # 點通過驗證，加入有效點列表
            # 統一精度到5位小數 (約10公尺精度)
            lat_decimal = round(record['latitude'] / 1000000.0, 5)
            lng_decimal = round(record['longitude'] / 1000000.0, 5)

            current_point = {
                'lat': lat_decimal,
                'lng': lng_decimal,
                'time': record['gps_time'].isoformat(),
            }

            valid_gps_points.append(current_point)

        logger.info(
            f"GPS filtering completed: {len(valid_gps_points)} valid points, {filtered_count} filtered out"
        )
        return valid_gps_points


class OSRMClient:
    """純粹的 OSRM API 調用"""

    @staticmethod
    def call_matching_api(coordinates: List[List[float]]) -> Dict:
        """調用 OSRM Matching API，提取座標和匹配資訊"""
        try:
            coords_str = ';'.join([f"{lng},{lat}" for lng, lat in coordinates])
            url = f"{settings.OSRM_BASE_URL}/match/v1/bicycle/{coords_str}"

            params = {
                'overview': 'full',
                'geometries': 'geojson',
                'annotations': 'false',
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('code') == 'Ok' and result.get('matchings'):
                # 提取所有匹配的幾何座標
                all_coordinates = []
                total_distance = 0
                weighted_confidence = 0

                for matching in result['matchings']:
                    matching_distance = matching.get('distance', 0)
                    matching_confidence = matching.get('confidence', 0)

                    # 累積總距離和加權信心分數
                    total_distance += matching_distance
                    weighted_confidence += matching_confidence * matching_distance

                    # 提取匹配的幾何座標
                    geometry = matching.get('geometry', {})
                    coordinates_list = geometry.get('coordinates', [])
                    if coordinates_list:
                        all_coordinates.extend(coordinates_list)

                # 計算加權平均信心分數
                average_confidence = (
                    weighted_confidence / total_distance if total_distance > 0 else 0.0
                )

                # 返回座標、tracepoints和匹配資訊
                return {
                    'success': True,
                    'coordinates': all_coordinates,
                    'tracepoints': result.get('tracepoints', []),
                    'total_distance': total_distance,
                    'average_confidence': average_confidence,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message', 'No matchings found'),
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}


class OSRMRecursiveFallbackStrategy:
    """遞歸分治匹配策略"""

    DEFAULT_MAX_RECURSION_DEPTH = 3
    MIN_COORDINATE_LENGTH = 3

    @classmethod
    def _calculate_dynamic_max_depth(cls, ride_duration_minutes: int = None) -> int:
        """根據騎乘時長計算動態最大遞歸深度"""
        if ride_duration_minutes is None:
            return cls.DEFAULT_MAX_RECURSION_DEPTH

        if ride_duration_minutes <= 15:
            return 2
        elif ride_duration_minutes <= 30:
            return 3
        elif ride_duration_minutes <= 90:
            return 4
        else:
            return 5

    @classmethod
    def _calculate_ride_duration(cls, start_time: str, end_time: str) -> int:
        """計算騎乘時長（分鐘）"""
        try:
            time_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%S.%f%z',
            ]

            start_dt = None
            end_dt = None

            for fmt in time_formats:
                try:
                    start_dt = datetime.strptime(start_time, fmt)
                    end_dt = datetime.strptime(end_time, fmt)
                    break
                except ValueError:
                    continue

            if start_dt and end_dt:
                duration = end_dt - start_dt
                return int(duration.total_seconds() / 60)  # 轉換為分鐘
            else:
                logger.warning(f"Unable to parse time format: {start_time}, {end_time}")
                return cls.DEFAULT_MAX_RECURSION_DEPTH

        except Exception as e:
            logger.error(f"Error calculating ride duration: {e}")
            return cls.DEFAULT_MAX_RECURSION_DEPTH

    @classmethod
    def match_with_recursive_split(
        cls, coordinates: List[List[float]], start_time: str, end_time: str
    ) -> Dict:
        """遞歸分治匹配主函數"""
        try:
            ride_duration_minutes = cls._calculate_ride_duration(start_time, end_time)
            max_depth = cls._calculate_dynamic_max_depth(ride_duration_minutes)

            result = cls._recursive_match(coordinates, 0, 0, max_depth)

            if result['success']:
                return {
                    'start_time': start_time,
                    'end_time': end_time,
                    'points_count': len(coordinates),
                    'fallback_strategy': f"recursive_depth_{result['depth']}",
                    'success': True,
                    'api_calls': result['api_calls'],
                    'coordinates': result['coordinates'],
                    'total_distance': result.get('total_distance', 0),
                    'average_confidence': result.get('average_confidence', 1.0),
                }

            return {
                'start_time': start_time,
                'end_time': end_time,
                'points_count': len(coordinates),
                'method': 'recursive_steps',
                'fallback_strategy': 'recursive_failed',
                'success': False,
                'error': result.get('error', 'Recursive matching failed'),
            }

        except Exception as e:
            logger.error(f"Recursive matching error: {e}")
            return {
                'start_time': start_time,
                'end_time': end_time,
                'points_count': len(coordinates),
                'method': 'recursive_steps',
                'fallback_strategy': 'recursive_error',
                'success': False,
                'error': str(e),
            }

    @classmethod
    def _recursive_match(
        cls, coordinates: List[List[float]], depth: int, api_calls: int, max_depth: int
    ) -> Dict:
        if depth >= max_depth:
            return {
                'success': False,
                'error': f'Max recursion depth reached ({max_depth})',
                'api_calls': api_calls,
            }

        if len(coordinates) < cls.MIN_COORDINATE_LENGTH:
            return {
                'success': False,
                'error': 'Segment too short',
                'api_calls': api_calls,
            }

        result = OSRMClient.call_matching_api(coordinates)
        api_calls += 1

        if result['success'] and result.get('coordinates'):
            failed_ranges = cls._detect_failed_ranges_from_tracepoints(
                result.get('tracepoints', []), len(coordinates)
            )

            if not failed_ranges:
                # 完全成功，所有點都匹配
                # 標記所有座標為匹配的
                marked_coordinates = [
                    {'coord': coord, 'is_mock': False}
                    for coord in result['coordinates']
                ]
                return {
                    'success': True,
                    'coordinates': marked_coordinates,
                    'total_distance': result.get('total_distance', 0),
                    'average_confidence': result.get('average_confidence', 1.0),
                    'depth': depth,
                    'api_calls': api_calls,
                }
            else:
                # 有匹配失敗的區間，需要重新匹配
                return cls._handle_failed_ranges_rematch(
                    coordinates, result, failed_ranges, depth, api_calls, max_depth
                )
        else:
            # 完全失敗，二分切割
            return cls._handle_binary_split(coordinates, depth, api_calls, max_depth)

    @classmethod
    def _detect_failed_ranges_from_tracepoints(
        cls, tracepoints: List, total_points: int
    ) -> List[tuple]:
        """從tracepoints檢測匹配失敗的區間"""
        if not tracepoints:
            # 如果沒有tracepoints，表示全部失敗
            return [(0, total_points - 1)] if total_points > 0 else []

        failed_ranges = []
        start_idx = None

        for i, point in enumerate(tracepoints):
            if point is None:
                # 匹配失敗的點
                if start_idx is None:
                    start_idx = i
            else:
                # 匹配成功的點
                if start_idx is not None:
                    failed_ranges.append((start_idx, i - 1))
                    start_idx = None

        # 處理結尾的失敗區間
        if start_idx is not None:
            failed_ranges.append((start_idx, len(tracepoints) - 1))

        return failed_ranges

    @classmethod
    def _handle_failed_ranges_rematch(
        cls,
        coordinates: List[List[float]],
        success_result: Dict,
        failed_ranges: List[tuple],
        depth: int,
        api_calls: int,
        max_depth: int,
    ) -> Dict:
        """處理匹配失敗區間的重匹配"""
        # 建立結果座標陣列，按原始索引順序填入
        result_coordinates = [None] * len(coordinates)
        total_distance = success_result.get('total_distance', 0)
        total_weighted_confidence = (
            success_result.get('average_confidence', 1.0) * total_distance
        )
        total_api_calls = api_calls
        reached_depth = depth

        # 1. 建立失敗區間索引集合
        failed_indices = set()
        for start_idx, end_idx in failed_ranges:
            failed_indices.update(range(start_idx, end_idx + 1))

        # 2. 填入成功匹配的座標
        matched_coords = success_result.get('coordinates', [])
        success_coord_idx = 0

        for i in range(len(coordinates)):
            if i not in failed_indices and success_coord_idx < len(matched_coords):
                result_coordinates[i] = {
                    'coord': matched_coords[success_coord_idx],
                    'is_mock': False,
                }
                success_coord_idx += 1

        # 3. 處理失敗區間
        for start_idx, end_idx in failed_ranges:
            failed_coords = coordinates[start_idx : end_idx + 1]

            # 遞歸重新匹配失敗區間
            rematch_result = cls._recursive_match(
                failed_coords, depth + 1, 0, max_depth
            )
            total_api_calls += rematch_result['api_calls']
            reached_depth = max(reached_depth, rematch_result.get('depth', depth))

            if rematch_result['success']:
                # 填入重匹配成功的座標
                rematch_coords = rematch_result.get('coordinates', [])
                for i, coord_data in enumerate(rematch_coords):
                    if start_idx + i < len(result_coordinates):
                        result_coordinates[start_idx + i] = coord_data

                rematch_distance = rematch_result.get('total_distance', 0)
                rematch_confidence = rematch_result.get('average_confidence', 1.0)
                total_distance += rematch_distance
                total_weighted_confidence += rematch_confidence * rematch_distance
            else:
                # 填入 mock 座標
                for i, coord in enumerate(failed_coords):
                    if start_idx + i < len(result_coordinates):
                        result_coordinates[start_idx + i] = {
                            'coord': coord,
                            'is_mock': True,
                        }

                mock_distance = CoordinateDistanceCalculator.calculate_total_distance(
                    failed_coords
                )
                total_distance += mock_distance
                # mock 信心分數為 0
                logger.warning(
                    f"Using mock coordinates for failed range {start_idx}-{end_idx}: {rematch_result.get('error')}"
                )

        # 4. 過濾掉 None 值並返回結果
        all_coordinates = [coord for coord in result_coordinates if coord is not None]
        final_confidence = total_weighted_confidence / total_distance

        return {
            'success': True,
            'coordinates': all_coordinates,
            'total_distance': total_distance,
            'average_confidence': final_confidence,
            'depth': reached_depth,
            'api_calls': total_api_calls,
        }

    @classmethod
    def _handle_binary_split(
        cls, coordinates: List[List[float]], depth: int, api_calls: int, max_depth: int
    ) -> Dict:
        """處理二分切割"""
        if len(coordinates) < cls.MIN_COORDINATE_LENGTH * 2:
            return {
                'success': False,
                'error': 'Cannot split further',
                'api_calls': api_calls,
            }

        # 從中點切割
        mid_idx = len(coordinates) // 2

        # 遞歸匹配左半段
        left_coords = coordinates[: mid_idx + 1]  # 包含中點
        left_result = cls._recursive_match(left_coords, depth + 1, 0, max_depth)

        # 遞歸匹配右半段
        right_coords = coordinates[mid_idx:]  # 包含中點
        right_result = cls._recursive_match(right_coords, depth + 1, 0, max_depth)

        total_api_calls = (
            api_calls + left_result['api_calls'] + right_result['api_calls']
        )

        if left_result['success'] and right_result['success']:
            # 合併兩個成功的結果
            combined_coordinates = left_result.get(
                'coordinates', []
            ) + right_result.get('coordinates', [])
            combined_distance = left_result.get('total_distance', 0) + right_result.get(
                'total_distance', 0
            )

            # 計算加權平均信心分數
            left_weight = left_result.get('total_distance', 0)
            right_weight = right_result.get('total_distance', 0)
            if combined_distance > 0:
                combined_confidence = (
                    left_result.get('average_confidence', 1.0) * left_weight
                    + right_result.get('average_confidence', 1.0) * right_weight
                ) / combined_distance
            else:
                combined_confidence = 1.0

            return {
                'success': True,
                'coordinates': combined_coordinates,
                'total_distance': combined_distance,
                'average_confidence': combined_confidence,
                'depth': max(left_result['depth'], right_result['depth']),
                'api_calls': total_api_calls,
            }
        elif left_result['success']:
            return {
                'success': True,
                'coordinates': left_result.get('coordinates', []),
                'total_distance': left_result.get('total_distance', 0),
                'average_confidence': left_result.get('average_confidence', 1.0),
                'depth': left_result['depth'],
                'api_calls': total_api_calls,
            }
        elif right_result['success']:
            return {
                'success': True,
                'coordinates': right_result.get('coordinates', []),
                'total_distance': right_result.get('total_distance', 0),
                'average_confidence': right_result.get('average_confidence', 1.0),
                'depth': right_result['depth'],
                'api_calls': total_api_calls,
            }
        else:
            # 兩邊都失敗，使用原始座標作為 mock
            mock_distance = CoordinateDistanceCalculator.calculate_total_distance(
                coordinates
            )
            # 標記所有座標為 mock
            mock_marked_coords = [
                {'coord': coord, 'is_mock': True} for coord in coordinates
            ]
            return {
                'success': True,  # 改為 True，因為我們有 fallback
                'coordinates': mock_marked_coords,  # 使用標記的原始座標
                'total_distance': mock_distance,  # 計算 mock 座標的實際距離
                'average_confidence': 0.0,  # mock 的信心分數為 0
                'depth': depth,
                'api_calls': total_api_calls,
            }


class OSRMService:
    @staticmethod
    def map_matching_with_fallback(
        coordinates: List[List[float]], start_time: str, end_time: str
    ) -> Dict:
        """整條軌跡遞歸分治匹配"""
        total_points = len(coordinates)
        logger.info(f"Starting recursive OSRM matching with {total_points} points")

        return OSRMRecursiveFallbackStrategy.match_with_recursive_split(
            coordinates, start_time, end_time
        )

    @staticmethod
    def extract_matched_data(osrm_result: Dict) -> Dict:
        """
        從 OSRM 結果提取用於 RouteMatchResult 的資料

        Args:
            osrm_result: OSRM 匹配結果

        Returns:
            包含 geometry_coordinates, start_point, end_point, distance_meters 等資料的字典
        """
        try:
            marked_coordinates = osrm_result.get('coordinates', [])
            if not marked_coordinates:
                logger.warning('No coordinates found in OSRM result')
                return {}

            # 提取純座標列表用於幾何對象
            all_coordinates = [item['coord'] for item in marked_coordinates]

            total_distance = osrm_result.get('total_distance', 0)
            average_confidence = osrm_result.get('average_confidence', 1.0)

            result_data = {
                'geometry_coordinates': all_coordinates,
                'marked_coordinates': marked_coordinates,  # 包含 mock 標記的座標
                'start_point': all_coordinates[0] if all_coordinates else None,
                'end_point': all_coordinates[-1] if all_coordinates else None,
                'distance_meters': total_distance,
                'average_confidence': average_confidence,
                'fallback_strategy': osrm_result.get('fallback_strategy', {}),
            }

            logger.info(
                f"Extracted {len(all_coordinates)} coordinates with confidence {average_confidence}"
            )
            return result_data

        except Exception as e:
            logger.error(f"Error extracting match result data: {e}")
            return {}


class RouteAnalysisService:
    """路線分析服務 - 將GPS軌跡轉換為RouteMatchResult和GeometryCoordinate統計"""

    @staticmethod
    def analyze_ride_route(ride_session_id: int) -> Dict:
        """
        分析騎乘軌跡並建立路段記錄

        Args:
            ride_session_id: RideSession ID

        Returns:
            分析結果
        """
        try:
            ride_session = RideSession.objects.get(id=ride_session_id)

            if not ride_session.gps_trajectory:
                return {'success': False, 'error': 'No GPS trajectory data found'}

            logger.info(f"Analyzing trajectory for RideSession {ride_session_id}")

            # 1. 準備座標數據 [[lng, lat], [lng, lat], ...]
            coordinates = [
                [point['lng'], point['lat']] for point in ride_session.gps_trajectory
            ]

            if len(coordinates) < 2:
                return {
                    'success': False,
                    'error': 'Insufficient GPS points for route matching',
                }

            # 2. OSRM Map Matching
            start_time = ride_session.gps_trajectory[0]['time']
            end_time = ride_session.gps_trajectory[-1]['time']
            osrm_result = OSRMService.map_matching_with_fallback(
                coordinates, start_time, end_time
            )

            if not osrm_result['success']:
                return {
                    'success': False,
                    'error': f"OSRM Map Matching failed: {osrm_result.get('error', 'Unknown error')}",
                }

            # 3. 提取匹配資料
            matched_data = OSRMService.extract_matched_data(osrm_result)

            if not matched_data:
                return {
                    'success': False,
                    'error': 'No matched data extracted from OSRM result',
                }

            # 4. 建立 RouteMatchResult
            geometry_coordinates = matched_data['geometry_coordinates']
            geometry = LineString(geometry_coordinates, srid=4326)
            start_point = Point(matched_data['start_point'], srid=4326)
            end_point = Point(matched_data['end_point'], srid=4326)

            route_match_result = RouteMatchResult.objects.create(
                ride_session=ride_session,
                geometry=geometry,
                start_point=start_point,
                end_point=end_point,
                distance_meters=matched_data['distance_meters'],
                average_confidence=matched_data['average_confidence'],
                fallback_strategy=matched_data.get('fallback_strategy', {}),
                is_sync_geometry_coordinate=False,
            )

            # 5. 處理座標去重和儲存，同時觸發時間統計更新
            try:
                GeometryCoordinateService.process_and_deduplicate_coordinates(
                    matched_data['marked_coordinates'],
                    ride_session.bike_rental.end_time,
                )

                # 6. 標記統計已完成，清理重試資訊
                route_match_result.is_sync_geometry_coordinate = True
                route_match_result.resync_details = None  # 清除重試資訊
                route_match_result.save(
                    update_fields=['is_sync_geometry_coordinate', 'resync_details']
                )

            except Exception as coord_error:
                # 座標處理失敗，保存重試所需的資訊
                logger.warning(
                    f"Coordinate processing failed for RouteMatchResult {route_match_result.id}: {coord_error}"
                )

                # 保存 marked_coordinates 的 is_mock 資訊供重試使用
                resync_data = {
                    'marked_coordinates': matched_data['marked_coordinates'],
                    'ride_end_time': ride_session.bike_rental.end_time.isoformat()
                    if ride_session.bike_rental.end_time
                    else None,
                    'error': str(coord_error),
                    'failed_at': timezone.now().isoformat(),
                }

                route_match_result.resync_details = resync_data
                route_match_result.save(update_fields=['resync_details'])

                # 重新拋出異常，讓上層知道處理失敗
                raise coord_error

            logger.info(
                f"Successfully analyzed trajectory for RideSession {ride_session_id}: "
                f"Created RouteMatchResult {route_match_result.id}"
            )

            return {
                'success': True,
                'ride_session_id': ride_session_id,
                'route_match_result_id': route_match_result.id,
            }

        except RideSession.DoesNotExist:
            return {
                'success': False,
                'error': f'RideSession {ride_session_id} not found',
            }
        except Exception as e:
            logger.error(
                f"Error analyzing trajectory for RideSession {ride_session_id}: {e}"
            )
            return {'success': False, 'error': str(e)}


class GeometryCoordinateService:
    """幾何座標服務 - 處理座標距離計算、去重和儲存"""

    TOLERANCE_NEARBY_METERS = 10.0  # 配合5位小數精度 (約10公尺)

    @classmethod
    def process_and_deduplicate_coordinates(
        cls, marked_coordinates: List[Dict], ride_time: datetime = None
    ) -> Dict:
        """
        處理座標並去重，將距離很近的點視為同一個點

        Args:
            marked_coordinates: 包含座標和 mock 標記的列表
            ride_time: 騎乘時間，用於時間統計

        Returns:
            統計結果
        """
        # 1. 內部去重：先處理這次座標中相近的點
        internal_deduplicated = cls._deduplicate_internal_coordinates(
            marked_coordinates
        )

        # 2. 準備查詢範圍內的現有座標
        existing_coords_qs = cls._get_existing_coordinates_qs_in_area(
            internal_deduplicated
        )

        # 3. 批次處理：分類要更新的和要新增的
        coords_to_update = defaultdict(int)  # {coord_id: additional_count}
        coords_to_create = []

        for coord_data in internal_deduplicated:
            # 統一精度到5位小數 (約10公尺精度)
            lat = round(coord_data['lat'], 5)
            lng = round(coord_data['lng'], 5)
            is_mock = coord_data['is_mock']
            count = coord_data['count']

            existing_coord = cls._find_closest_existing_coord(
                lat, lng, existing_coords_qs
            )

            if existing_coord:
                coords_to_update[existing_coord.id] += count
            else:
                coords_to_create.append(
                    GeometryCoordinate(
                        latitude=lat,
                        longitude=lng,
                        is_mock=is_mock,
                        total_usage_count=count,
                        point=Point(lng, lat, srid=4326),
                    )
                )

        # 4. 批次更新現有座標
        if coords_to_update:
            coord_ids = list(coords_to_update.keys())
            coords_to_update_objs = GeometryCoordinate.objects.filter(id__in=coord_ids)

            update_list = []
            for coord in coords_to_update_objs:
                coord.total_usage_count += coords_to_update[coord.id]
                update_list.append(coord)

            GeometryCoordinate.objects.bulk_update(update_list, ['total_usage_count'])

        # 5. 批次創建新座標 (使用事務鎖避免併發衝突)
        created_coords = []
        if coords_to_create:
            from django.db import transaction

            with transaction.atomic():
                # 先鎖定可能重複的座標，讓其他併發事務等待
                coords_to_lock = []
                for coord in coords_to_create:
                    coords_to_lock.append((coord.latitude, coord.longitude))

                if coords_to_lock:
                    # 使用 select_for_update 鎖定可能衝突的座標
                    locked_coords = (
                        GeometryCoordinate.objects.select_for_update().filter(
                            latitude__in=[lat for lat, lng in coords_to_lock],
                            longitude__in=[lng for lat, lng in coords_to_lock],
                        )
                    )
                    # 觸發查詢執行鎖定
                    list(locked_coords)

                # 在鎖定保護下執行批次創建
                created_coords = GeometryCoordinate.objects.bulk_create(
                    coords_to_create
                )

        # 6. 觸發時間統計更新
        if ride_time:
            all_affected_coords = []

            if coords_to_update:
                updated_coords = GeometryCoordinate.objects.filter(
                    id__in=coords_to_update.keys()
                )
                all_affected_coords.extend(updated_coords)

            if created_coords:
                all_affected_coords.extend(created_coords)

            if all_affected_coords:
                GeometryCoordinateTimeStatisticsService.update_coordinate_statistics(
                    all_affected_coords, ride_time
                )

        return {
            'updated_count': len(coords_to_update),
            'created_count': len(coords_to_create),
            'total_processed': len(internal_deduplicated),
        }

    @classmethod
    def _deduplicate_internal_coordinates(
        cls, marked_coordinates: List[Dict]
    ) -> List[Dict]:
        """
        內部去重：沿著路線檢查相鄰座標，過濾距離太近的點

        Returns:
            List[{'lat': float, 'lng': float, 'is_mock': bool, 'count': int}]
        """
        if not marked_coordinates:
            return []

        result = []

        for item in marked_coordinates:
            coord = item['coord']
            is_mock = item['is_mock']
            # 統一精度到5位小數 (約10公尺精度)
            lat = round(coord[1], 5)
            lng = round(coord[0], 5)

            if result and cls._are_coordinates_close(
                lat, lng, result[-1]['lat'], result[-1]['lng']
            ):
                continue

            result.append({'lat': lat, 'lng': lng, 'is_mock': is_mock, 'count': 1})

        return result

    @classmethod
    def _are_coordinates_close(
        cls, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> bool:
        """
        檢查兩個座標是否在容差範圍內
        使用 CoordinateDistanceCalculator 的距離計算
        """
        distance_meters = CoordinateDistanceCalculator.calculate_distance(
            [lng1, lat1], [lng2, lat2]
        )
        return distance_meters <= cls.TOLERANCE_NEARBY_METERS

    @classmethod
    def _get_existing_coordinates_qs_in_area(cls, deduplicated_coords: List[Dict]):
        """
        取得指定區域內的現有座標

        Returns:
            QuerySet[GeometryCoordinate]
        """
        if not deduplicated_coords:
            return GeometryCoordinate.objects.none()

        lats = [c['lat'] for c in deduplicated_coords]
        lngs = [c['lng'] for c in deduplicated_coords]

        min_lat, max_lat = min(lats) - 0.001, max(lats) + 0.001
        min_lng, max_lng = min(lngs) - 0.001, max(lngs) + 0.001

        return GeometryCoordinate.objects.filter(
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lng,
            longitude__lte=max_lng,
        )

    @classmethod
    def _find_closest_existing_coord(
        cls, lat: float, lng: float, existing_coords_qs
    ) -> Optional[GeometryCoordinate]:
        """
        從範圍內的座標中尋找最近的座標
        """
        query_point = Point(lng, lat, srid=4326)

        # 使用 PostGIS 直接查詢在容差範圍內的座標
        from django.contrib.gis.db.models.functions import Distance as DistanceFunction

        nearby_coords = (
            existing_coords_qs.filter(
                point__distance_lte=(
                    query_point,
                    Distance(m=cls.TOLERANCE_NEARBY_METERS),
                )
            )
            .annotate(distance=DistanceFunction('point', query_point))
            .order_by('distance')
        )

        return nearby_coords.first()


class GeometryCoordinateTimeStatisticsService:
    """
    座標時間統計服務
    負責聚合和管理座標的時間級別使用統計
    """

    @classmethod
    def update_coordinate_statistics(
        cls, geometry_coordinates: List[GeometryCoordinate], ride_time: datetime
    ):
        """
        更新座標統計

        Args:
            geometry_coordinates: 座標物件列表
            ride_time: 騎乘時間
        """
        try:
            if not geometry_coordinates:
                logger.warning('No geometry coordinates provided for statistics update')
                return

            # 批次更新小時級別統計
            cls._batch_update_hourly_stats(geometry_coordinates, ride_time)

            # 批次更新日級別統計
            cls._batch_update_daily_stats(geometry_coordinates, ride_time)

            logger.info(
                f"Updated coordinate statistics for {len(geometry_coordinates)} coordinates"
            )

        except Exception as e:
            logger.error(f"Error updating coordinate statistics: {str(e)}")

    @classmethod
    def _batch_update_hourly_stats(
        cls, geometry_coordinates: List[GeometryCoordinate], ride_time: datetime
    ):
        """
        批次更新小時級別統計

        Args:
            geometry_coordinates: 座標物件列表
            ride_time: 騎乘時間
        """
        # 將時間調整為整點（移除分鐘和秒）
        hour_timestamp = ride_time.replace(minute=0, second=0, microsecond=0)

        # 批次查詢現有統計記錄
        coord_ids = [coord.id for coord in geometry_coordinates]
        existing_stats = {
            stat.geometry_coordinate_id: stat
            for stat in HourlyGeometryCoordinateStatistics.objects.filter(
                geometry_coordinate_id__in=coord_ids, collected_time=hour_timestamp
            )
        }

        stats_to_create = []
        stats_to_update = []

        for coord in geometry_coordinates:
            if coord.id in existing_stats:
                # 更新現有記錄
                stat = existing_stats[coord.id]
                stat.usage_count = F('usage_count') + 1
                stats_to_update.append(stat)
            else:
                # 創建新記錄
                stats_to_create.append(
                    HourlyGeometryCoordinateStatistics(
                        geometry_coordinate=coord,
                        collected_time=hour_timestamp,
                        usage_count=1,
                    )
                )

        # 批次操作
        if stats_to_create:
            HourlyGeometryCoordinateStatistics.objects.bulk_create(stats_to_create)

        if stats_to_update:
            HourlyGeometryCoordinateStatistics.objects.bulk_update(
                stats_to_update, ['usage_count', 'updated_at']
            )

    @classmethod
    def _batch_update_daily_stats(
        cls, geometry_coordinates: List[GeometryCoordinate], ride_time: datetime
    ):
        """
        批次更新日級別統計

        Args:
            geometry_coordinates: 座標物件列表
            ride_time: 騎乘時間
        """
        # 取得日期
        date = ride_time.date()

        # 批次查詢現有統計記錄
        coord_ids = [coord.id for coord in geometry_coordinates]
        existing_stats = {
            stat.geometry_coordinate_id: stat
            for stat in DailyGeometryCoordinateStatistics.objects.filter(
                geometry_coordinate_id__in=coord_ids, collected_time=date
            )
        }

        stats_to_create = []
        stats_to_update = []

        for coord in geometry_coordinates:
            if coord.id in existing_stats:
                # 更新現有記錄
                stat = existing_stats[coord.id]
                stat.usage_count = F('usage_count') + 1
                stats_to_update.append(stat)
            else:
                # 創建新記錄
                stats_to_create.append(
                    DailyGeometryCoordinateStatistics(
                        geometry_coordinate=coord, collected_time=date, usage_count=1
                    )
                )

        # 批次操作
        if stats_to_create:
            DailyGeometryCoordinateStatistics.objects.bulk_create(stats_to_create)

        if stats_to_update:
            DailyGeometryCoordinateStatistics.objects.bulk_update(
                stats_to_update, ['usage_count', 'updated_at']
            )
