"""
Tests for coordinate time statistics
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from statistic.models import (
    DailyGeometryCoordinateStatistics,
    GeometryCoordinate,
    HourlyGeometryCoordinateStatistics,
)
from statistic.services import GeometryCoordinateTimeStatisticsService
from statistic.tests.base import BaseStatisticTestWithFixtures


class GeometryCoordinateTimeStatisticsServiceTest(BaseStatisticTestWithFixtures):
    """座標時間統計服務測試"""

    def setUp(self):
        super().setUp()
        # 創建測試座標
        self.test_coords = [
            GeometryCoordinate.objects.create(
                latitude=25.042500,
                longitude=121.565000,
                is_mock=False,
                total_usage_count=1,
            ),
            GeometryCoordinate.objects.create(
                latitude=25.042600,
                longitude=121.565100,
                is_mock=False,
                total_usage_count=1,
            ),
            GeometryCoordinate.objects.create(
                latitude=25.042700,
                longitude=121.565200,
                is_mock=True,
                total_usage_count=1,
            ),
        ]

        # 測試時間
        self.test_time = timezone.make_aware(datetime(2024, 1, 15, 14, 30, 0))

    def test_batch_update_hourly_stats_new_records(self):
        """測試批次更新小時統計 - 新記錄"""
        # 確保沒有現有記錄
        self.assertEqual(HourlyGeometryCoordinateStatistics.objects.count(), 0)

        # 執行批次更新
        GeometryCoordinateTimeStatisticsService._batch_update_hourly_stats(
            self.test_coords, self.test_time
        )

        # 檢查結果
        hourly_stats = HourlyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(hourly_stats.count(), 3)

        # 檢查時間被調整為整點
        expected_hour = self.test_time.replace(minute=0, second=0, microsecond=0)
        for stat in hourly_stats:
            self.assertEqual(stat.collected_time, expected_hour)
            self.assertEqual(stat.usage_count, 1)

    def test_batch_update_hourly_stats_existing_records(self):
        """測試批次更新小時統計 - 更新現有記錄"""
        # 創建現有記錄
        hour_timestamp = self.test_time.replace(minute=0, second=0, microsecond=0)
        existing_stat = HourlyGeometryCoordinateStatistics.objects.create(
            geometry_coordinate=self.test_coords[0],
            collected_time=hour_timestamp,
            usage_count=5,
        )

        # 執行批次更新
        GeometryCoordinateTimeStatisticsService._batch_update_hourly_stats(
            self.test_coords, self.test_time
        )

        # 檢查結果
        hourly_stats = HourlyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(hourly_stats.count(), 3)

        # 檢查現有記錄被更新
        existing_stat.refresh_from_db()
        self.assertEqual(existing_stat.usage_count, 6)  # 5 + 1

        # 檢查新記錄
        new_stats = HourlyGeometryCoordinateStatistics.objects.exclude(
            id=existing_stat.id
        )
        self.assertEqual(new_stats.count(), 2)
        for stat in new_stats:
            self.assertEqual(stat.usage_count, 1)

    def test_batch_update_daily_stats_new_records(self):
        """測試批次更新日統計 - 新記錄"""
        # 確保沒有現有記錄
        self.assertEqual(DailyGeometryCoordinateStatistics.objects.count(), 0)

        # 執行批次更新
        GeometryCoordinateTimeStatisticsService._batch_update_daily_stats(
            self.test_coords, self.test_time
        )

        # 檢查結果
        daily_stats = DailyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(daily_stats.count(), 3)

        # 檢查日期
        expected_date = self.test_time.date()
        for stat in daily_stats:
            self.assertEqual(stat.collected_time, expected_date)
            self.assertEqual(stat.usage_count, 1)

    def test_batch_update_daily_stats_existing_records(self):
        """測試批次更新日統計 - 更新現有記錄"""
        # 創建現有記錄
        date = self.test_time.date()
        existing_stat = DailyGeometryCoordinateStatistics.objects.create(
            geometry_coordinate=self.test_coords[0], collected_time=date, usage_count=3
        )

        # 執行批次更新
        GeometryCoordinateTimeStatisticsService._batch_update_daily_stats(
            self.test_coords, self.test_time
        )

        # 檢查結果
        daily_stats = DailyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(daily_stats.count(), 3)

        # 檢查現有記錄被更新
        existing_stat.refresh_from_db()
        self.assertEqual(existing_stat.usage_count, 4)  # 3 + 1

        # 檢查新記錄
        new_stats = DailyGeometryCoordinateStatistics.objects.exclude(
            id=existing_stat.id
        )
        self.assertEqual(new_stats.count(), 2)
        for stat in new_stats:
            self.assertEqual(stat.usage_count, 1)

    def test_update_coordinate_statistics_complete_flow(self):
        """測試完整的座標統計更新流程"""
        # 執行統計更新
        GeometryCoordinateTimeStatisticsService.update_coordinate_statistics(
            self.test_coords, self.test_time
        )

        # 檢查小時統計
        hourly_stats = HourlyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(hourly_stats.count(), 3)

        # 檢查日統計
        daily_stats = DailyGeometryCoordinateStatistics.objects.all()
        self.assertEqual(daily_stats.count(), 3)

        # 檢查關聯關係
        for coord in self.test_coords:
            hourly_stat = HourlyGeometryCoordinateStatistics.objects.get(
                geometry_coordinate=coord
            )
            daily_stat = DailyGeometryCoordinateStatistics.objects.get(
                geometry_coordinate=coord
            )
            self.assertEqual(hourly_stat.usage_count, 1)
            self.assertEqual(daily_stat.usage_count, 1)

    def test_update_coordinate_statistics_empty_list(self):
        """測試空座標列表"""
        with patch('statistic.services.logger'):
            GeometryCoordinateTimeStatisticsService.update_coordinate_statistics(
                [], self.test_time
            )

        # 不應該創建任何記錄
        self.assertEqual(HourlyGeometryCoordinateStatistics.objects.count(), 0)
        self.assertEqual(DailyGeometryCoordinateStatistics.objects.count(), 0)

    def test_hourly_stats_data_structure(self):
        """測試小時統計資料結構"""
        # 創建測試資料
        hour_timestamp = self.test_time.replace(minute=0, second=0, microsecond=0)

        for i, coord in enumerate(self.test_coords):
            HourlyGeometryCoordinateStatistics.objects.create(
                geometry_coordinate=coord,
                collected_time=hour_timestamp,
                usage_count=i + 1,  # 1, 2, 3
            )

        # 檢查資料建立
        hourly_stats = HourlyGeometryCoordinateStatistics.objects.all().order_by(
            '-usage_count'
        )
        self.assertEqual(hourly_stats.count(), 3)

        # 檢查資料結構和排序
        self.assertEqual(hourly_stats[0].usage_count, 3)  # 最高使用次數
        self.assertEqual(hourly_stats[1].usage_count, 2)
        self.assertEqual(hourly_stats[2].usage_count, 1)

        # 檢查時間正確性
        for stat in hourly_stats:
            self.assertEqual(stat.collected_time, hour_timestamp)

    def test_daily_stats_data_structure(self):
        """測試日統計資料結構"""
        # 創建測試資料
        date = self.test_time.date()

        for i, coord in enumerate(self.test_coords):
            DailyGeometryCoordinateStatistics.objects.create(
                geometry_coordinate=coord,
                collected_time=date,
                usage_count=i + 2,  # 2, 3, 4
            )

        # 檢查資料建立
        daily_stats = DailyGeometryCoordinateStatistics.objects.all().order_by(
            '-usage_count'
        )
        self.assertEqual(daily_stats.count(), 3)

        # 檢查資料結構和排序
        self.assertEqual(daily_stats[0].usage_count, 4)  # 最高使用次數
        self.assertEqual(daily_stats[1].usage_count, 3)
        self.assertEqual(daily_stats[2].usage_count, 2)

        # 檢查日期正確性
        for stat in daily_stats:
            self.assertEqual(stat.collected_time, date)

    def test_time_stats_model_relationships(self):
        """測試時間統計模型關聯關係"""
        coord = self.test_coords[0]

        # 創建小時和日統計
        hour_timestamp = self.test_time.replace(minute=0, second=0, microsecond=0)
        date = self.test_time.date()

        hourly_stat = HourlyGeometryCoordinateStatistics.objects.create(
            geometry_coordinate=coord, collected_time=hour_timestamp, usage_count=5
        )

        daily_stat = DailyGeometryCoordinateStatistics.objects.create(
            geometry_coordinate=coord, collected_time=date, usage_count=10
        )

        # 檢查反向關聯
        self.assertEqual(coord.hourly_stats.count(), 1)
        self.assertEqual(coord.daily_stats.count(), 1)

        # 檢查關聯物件
        self.assertEqual(coord.hourly_stats.first(), hourly_stat)
        self.assertEqual(coord.daily_stats.first(), daily_stat)

    def test_mixed_mock_and_real_coordinates(self):
        """測試混合 mock 和真實座標的統計"""
        # 執行統計更新
        GeometryCoordinateTimeStatisticsService.update_coordinate_statistics(
            self.test_coords, self.test_time
        )

        # 檢查 mock 座標統計
        mock_coord = self.test_coords[2]  # is_mock=True
        mock_hourly_stat = HourlyGeometryCoordinateStatistics.objects.get(
            geometry_coordinate=mock_coord
        )
        mock_daily_stat = DailyGeometryCoordinateStatistics.objects.get(
            geometry_coordinate=mock_coord
        )

        self.assertEqual(mock_hourly_stat.usage_count, 1)
        self.assertEqual(mock_daily_stat.usage_count, 1)

        # 檢查真實座標統計
        real_coord = self.test_coords[0]  # is_mock=False
        real_hourly_stat = HourlyGeometryCoordinateStatistics.objects.get(
            geometry_coordinate=real_coord
        )
        real_daily_stat = DailyGeometryCoordinateStatistics.objects.get(
            geometry_coordinate=real_coord
        )

        self.assertEqual(real_hourly_stat.usage_count, 1)
        self.assertEqual(real_daily_stat.usage_count, 1)
