"""
Tests for coordinate statistics algorithm
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from statistic.models import (
    DailyGeometryCoordinateStatistics,
    GeometryCoordinate,
    HourlyGeometryCoordinateStatistics,
    RideSession,
    RouteMatchResult,
)
from statistic.services import (
    GeometryCoordinateService,
    GPSPointValidator,
    RouteAnalysisService,
    TrajectoryExtractionService,
)
from statistic.tests.base import BaseStatisticTestWithFixtures


class TrajectoryExtractionServiceTest(BaseStatisticTestWithFixtures):
    """軌跡提取服務測試"""

    def test_extract_gps_trajectory_success(self):
        """測試成功提取GPS軌跡"""
        result = TrajectoryExtractionService.extract_gps_trajectory(self.bike_rental_1)

        self.assertTrue(result['success'])
        self.assertEqual(result['total_raw_points'], 4)  # 4個點在時間範圍內
        self.assertEqual(result['valid_points'], 3)  # 3個有效點
        self.assertEqual(result['filtered_out'], 1)  # 1個無效點 (0,0 + RSSI=99)

        # 檢查 RideSession 更新
        self.ride_session_1.refresh_from_db()
        self.assertEqual(self.ride_session_1.raw_point_count, 4)
        self.assertEqual(self.ride_session_1.valid_point_count, 3)
        self.assertIsNotNone(self.ride_session_1.gps_trajectory)

    def test_extract_gps_trajectory_no_points(self):
        """測試沒有GPS點的情況"""
        result = TrajectoryExtractionService.extract_gps_trajectory(self.bike_rental_2)

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No GPS points found for this rental period')

    def test_gps_point_filtering(self):
        """測試GPS點過濾邏輯"""
        # 測試有效點
        valid_record = {
            'latitude': 25042500,
            'longitude': 121565000,
            'gps_time': 'fake_datetime',
            'rssi': 20,
        }
        is_valid, reason = GPSPointValidator.is_valid_point(valid_record, [])
        self.assertTrue(is_valid)
        self.assertEqual(reason, '')

        # 測試無效座標 (0,0)
        invalid_record_coords = {
            'latitude': 0,
            'longitude': 0,
            'gps_time': 'fake_datetime',
            'rssi': 20,
        }
        is_valid, reason = GPSPointValidator.is_valid_point(invalid_record_coords, [])
        self.assertFalse(is_valid)
        self.assertEqual(reason, 'Invalid coordinates (0,0)')

        # 測試信號品質差 (RSSI=99)
        invalid_record_rssi = {
            'latitude': 25042500,
            'longitude': 121565000,
            'gps_time': 'fake_datetime',
            'rssi': 99,
        }
        is_valid, reason = GPSPointValidator.is_valid_point(invalid_record_rssi, [])
        self.assertFalse(is_valid)
        self.assertEqual(reason, 'Poor GPS signal quality (RSSI=99)')


class RouteAnalysisServiceTest(BaseStatisticTestWithFixtures):
    """路線分析服務測試"""

    def test_analyze_ride_route_with_osrm_success(self):
        """測試使用OSRM成功分析路線"""
        # 先提取軌跡
        TrajectoryExtractionService.extract_gps_trajectory(self.bike_rental_1)

        # 模擬OSRM成功響應
        mock_patch, mock_get, mock_response = self.mock_osrm_success_response()
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None

        try:
            result = RouteAnalysisService.analyze_ride_route(self.ride_session_1.id)

            self.assertTrue(result['success'])
            self.assertEqual(result['ride_session_id'], self.ride_session_1.id)
            self.assertIn('route_match_result_id', result)

            # 檢查 RouteMatchResult 建立
            route_match_result = RouteMatchResult.objects.get(
                id=result['route_match_result_id']
            )
            self.assertEqual(route_match_result.ride_session, self.ride_session_1)
            self.assertAlmostEqual(route_match_result.distance_meters, 1250.5, places=1)
            self.assertAlmostEqual(
                route_match_result.average_confidence, 0.85, places=2
            )
            self.assertTrue(route_match_result.is_sync_geometry_coordinate)

            # 檢查 GeometryCoordinate 建立
            geometry_coords = GeometryCoordinate.objects.all()
            self.assertGreater(geometry_coords.count(), 0)
        finally:
            mock_patch.stop()

    def test_analyze_ride_route_without_gps_trajectory(self):
        """測試沒有GPS軌跡的情況"""
        result = RouteAnalysisService.analyze_ride_route(self.ride_session_1.id)

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No GPS trajectory data found')

    def test_analyze_ride_route_insufficient_points(self):
        """測試GPS點不足的情況"""
        # 設置只有一個點的軌跡
        self.ride_session_1.gps_trajectory = [
            {'lat': 25.042500, 'lng': 121.565000, 'time': '2024-01-15T10:00:00Z'}
        ]
        self.ride_session_1.save()

        result = RouteAnalysisService.analyze_ride_route(self.ride_session_1.id)

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Insufficient GPS points for route matching')


class GeometryCoordinateServiceTest(BaseStatisticTestWithFixtures):
    """幾何座標服務測試"""

    def test_process_and_deduplicate_coordinates(self):
        """測試座標處理和去重"""
        # 準備測試座標資料
        marked_coordinates = [
            {'coord': [121.565000, 25.042500], 'is_mock': False},
            {'coord': [121.565001, 25.042501], 'is_mock': False},  # 很接近上一個點
            {'coord': [121.565100, 25.042600], 'is_mock': False},
            {'coord': [121.565200, 25.042700], 'is_mock': True},  # mock 座標
            {'coord': [121.565300, 25.042800], 'is_mock': False},
        ]

        # 執行處理
        GeometryCoordinateService.process_and_deduplicate_coordinates(
            marked_coordinates
        )

        # 檢查結果
        geometry_coords = GeometryCoordinate.objects.all()
        self.assertGreater(geometry_coords.count(), 0)

        # 檢查是否有 mock 和非 mock 座標
        mock_coords = GeometryCoordinate.objects.filter(is_mock=True)
        non_mock_coords = GeometryCoordinate.objects.filter(is_mock=False)
        self.assertGreater(mock_coords.count(), 0)
        self.assertGreater(non_mock_coords.count(), 0)

    def test_internal_deduplication(self):
        """測試內部去重邏輯"""
        marked_coordinates = [
            {'coord': [121.565000, 25.042500], 'is_mock': False},
            {'coord': [121.565001, 25.042500], 'is_mock': False},  # 距離很近
            {'coord': [121.565100, 25.042600], 'is_mock': False},  # 距離較遠
        ]

        result = GeometryCoordinateService._deduplicate_internal_coordinates(
            marked_coordinates
        )

        # 第二個點應該被過濾掉
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['lat'], 25.042500)
        self.assertEqual(result[1]['lat'], 25.042600)

    def test_coordinate_distance_comparison(self):
        """測試座標距離比較"""
        # 測試相近的座標
        close_result = GeometryCoordinateService._are_coordinates_close(
            25.042500, 121.565000, 25.042501, 121.565001
        )
        self.assertTrue(close_result)

        # 測試距離較遠的座標
        far_result = GeometryCoordinateService._are_coordinates_close(
            25.042500, 121.565000, 25.043000, 121.566000
        )
        self.assertFalse(far_result)

    def test_find_closest_existing_coord(self):
        """測試尋找最近現有座標"""
        # 先建立一個座標
        existing_coord = GeometryCoordinate.objects.create(
            latitude=25.042500, longitude=121.565000, is_mock=False, total_usage_count=1
        )

        # 準備查詢範圍
        test_coords = [
            {'lat': 25.042501, 'lng': 121.565001, 'is_mock': False, 'count': 1}
        ]
        coords_qs = GeometryCoordinateService._get_existing_coordinates_qs_in_area(
            test_coords
        )

        # 尋找最近的座標
        closest = GeometryCoordinateService._find_closest_existing_coord(
            25.042501, 121.565001, coords_qs
        )

        self.assertEqual(closest, existing_coord)

    def test_coordinate_duplicate_ignores_is_mock(self):
        """測試座標重複檢查不考慮 is_mock 標記"""
        # 建立一個 mock 座標
        existing_coord = GeometryCoordinate.objects.create(
            latitude=25.042500,
            longitude=121.565000,
            is_mock=True,  # 這是 mock 座標
            total_usage_count=1,
        )

        # 嘗試新增一個非 mock 但位置相同的座標
        marked_coordinates = [
            {'coord': [121.565000, 25.042500], 'is_mock': False}  # 非 mock 但位置相同
        ]

        GeometryCoordinateService.process_and_deduplicate_coordinates(
            marked_coordinates
        )

        # 檢查應該更新現有座標而不是建立新的
        existing_coord.refresh_from_db()
        self.assertEqual(existing_coord.total_usage_count, 2)
        self.assertEqual(GeometryCoordinate.objects.count(), 1)

    def test_process_and_deduplicate_coordinates_with_time_statistics(self):
        """測試座標處理同時觸發時間統計"""
        # 準備測試座標資料
        marked_coordinates = [
            {'coord': [121.565000, 25.042500], 'is_mock': False},
            {'coord': [121.565100, 25.042600], 'is_mock': False},
            {'coord': [121.565200, 25.042700], 'is_mock': True},
        ]

        # 設定測試時間
        test_time = timezone.make_aware(datetime(2024, 1, 15, 14, 30, 0))

        # 執行處理（包含時間統計）
        result = GeometryCoordinateService.process_and_deduplicate_coordinates(
            marked_coordinates, test_time
        )

        # 檢查基本結果
        self.assertEqual(result['created_count'], 3)
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['total_processed'], 3)

        # 檢查座標建立
        geometry_coords = GeometryCoordinate.objects.all()
        self.assertEqual(geometry_coords.count(), 3)

        # 檢查小時統計建立
        hourly_stats = HourlyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(hourly_stats.count(), 3)

        expected_hour = test_time.replace(minute=0, second=0, microsecond=0)
        for stat in hourly_stats:
            self.assertEqual(stat.collected_time, expected_hour)
            self.assertEqual(stat.usage_count, 1)

        # 檢查日統計建立
        daily_stats = DailyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(daily_stats.count(), 3)

        expected_date = test_time.date()
        for stat in daily_stats:
            self.assertEqual(stat.collected_time, expected_date)
            self.assertEqual(stat.usage_count, 1)

    def test_process_and_deduplicate_coordinates_without_time(self):
        """測試不傳入時間時不觸發統計"""
        # 準備測試座標資料
        marked_coordinates = [
            {'coord': [121.565000, 25.042500], 'is_mock': False},
        ]

        # 執行處理（不傳入時間）
        result = GeometryCoordinateService.process_and_deduplicate_coordinates(
            marked_coordinates
        )

        # 檢查座標建立
        self.assertEqual(GeometryCoordinate.objects.count(), 1)

        # 檢查沒有時間統計建立
        self.assertEqual(HourlyGeometryCoordinateStatistics.objects.count(), 0)
        self.assertEqual(DailyGeometryCoordinateStatistics.objects.count(), 0)

    def test_process_and_deduplicate_coordinates_update_existing_with_time_stats(self):
        """測試更新現有座標時的時間統計"""
        # 先建立一個座標
        existing_coord = GeometryCoordinate.objects.create(
            latitude=25.042500, longitude=121.565000, is_mock=False, total_usage_count=1
        )

        # 設定測試時間
        test_time = timezone.make_aware(datetime(2024, 1, 15, 14, 30, 0))

        # 嘗試新增相同位置的座標
        marked_coordinates = [{'coord': [121.565000, 25.042500], 'is_mock': False}]

        result = GeometryCoordinateService.process_and_deduplicate_coordinates(
            marked_coordinates, test_time
        )

        # 檢查結果
        self.assertEqual(result['created_count'], 0)
        self.assertEqual(result['updated_count'], 1)

        # 檢查座標更新
        existing_coord.refresh_from_db()
        self.assertEqual(existing_coord.total_usage_count, 2)
        self.assertEqual(GeometryCoordinate.objects.count(), 1)

        # 檢查時間統計建立
        hourly_stats = HourlyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(hourly_stats.count(), 1)

        daily_stats = DailyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(daily_stats.count(), 1)

        # 檢查統計內容
        hourly_stat = hourly_stats.first()
        daily_stat = daily_stats.first()

        self.assertEqual(hourly_stat.geometry_coordinate, existing_coord)
        self.assertEqual(daily_stat.geometry_coordinate, existing_coord)
        self.assertEqual(hourly_stat.usage_count, 1)
        self.assertEqual(daily_stat.usage_count, 1)
