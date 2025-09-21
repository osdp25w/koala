"""
Tests for utility functions
"""
from django.test import TestCase

from utils.coordinate import CoordinateDistanceCalculator


class CoordinateDistanceCalculatorTest(TestCase):
    """座標距離計算器測試"""

    def test_calculate_distance_same_point(self):
        """測試相同點的距離"""
        point = [121.565000, 25.042500]
        distance = CoordinateDistanceCalculator.calculate_distance(point, point)
        self.assertEqual(distance, 0.0)

    def test_calculate_distance_known_points(self):
        """測試已知點之間的距離"""
        # 台北市政府到台北101大約1.5公里
        taipei_city_hall = [121.565000, 25.042500]
        taipei_101 = [121.565500, 25.046000]

        distance = CoordinateDistanceCalculator.calculate_distance(
            taipei_city_hall, taipei_101
        )

        # 距離應該大約在300-500米範圍內（這個座標差異）
        self.assertGreater(distance, 300)
        self.assertLess(distance, 600)

    def test_calculate_distance_precision(self):
        """測試距離計算精度"""
        point1 = [121.565000, 25.042500]
        point2 = [121.565001, 25.042501]  # 很小的差異

        distance = CoordinateDistanceCalculator.calculate_distance(point1, point2)

        # 非常小的座標差異應該產生很小的距離
        self.assertGreater(distance, 0)
        self.assertLess(distance, 2)  # 應該小於2米

    def test_calculate_total_distance_empty_list(self):
        """測試空列表的總距離"""
        distance = CoordinateDistanceCalculator.calculate_total_distance([])
        self.assertEqual(distance, 0.0)

    def test_calculate_total_distance_single_point(self):
        """測試單點的總距離"""
        coordinates = [[121.565000, 25.042500]]
        distance = CoordinateDistanceCalculator.calculate_total_distance(coordinates)
        self.assertEqual(distance, 0.0)

    def test_calculate_total_distance_multiple_points(self):
        """測試多點軌跡的總距離"""
        coordinates = [
            [121.565000, 25.042500],
            [121.565100, 25.042600],
            [121.565200, 25.042700],
            [121.565300, 25.042800],
        ]

        total_distance = CoordinateDistanceCalculator.calculate_total_distance(
            coordinates
        )

        # 計算各段距離
        segment1 = CoordinateDistanceCalculator.calculate_distance(
            coordinates[0], coordinates[1]
        )
        segment2 = CoordinateDistanceCalculator.calculate_distance(
            coordinates[1], coordinates[2]
        )
        segment3 = CoordinateDistanceCalculator.calculate_distance(
            coordinates[2], coordinates[3]
        )
        expected_total = segment1 + segment2 + segment3

        self.assertAlmostEqual(total_distance, expected_total, places=5)

    def test_coordinate_format(self):
        """測試座標格式要求 [lng, lat]"""
        # 確保使用正確的座標格式 [經度, 緯度]
        lng, lat = 121.565000, 25.042500
        point1 = [lng, lat]
        point2 = [lng + 0.001, lat + 0.001]

        distance = CoordinateDistanceCalculator.calculate_distance(point1, point2)

        # 應該能正常計算距離
        self.assertGreater(distance, 0)
        self.assertIsInstance(distance, float)

    def test_negative_coordinates(self):
        """測試負座標的處理"""
        # 測試南半球或西半球的座標
        point1 = [-121.565000, -25.042500]
        point2 = [-121.565100, -25.042600]

        distance = CoordinateDistanceCalculator.calculate_distance(point1, point2)

        # 應該能正常計算距離
        self.assertGreater(distance, 0)
        self.assertIsInstance(distance, float)
