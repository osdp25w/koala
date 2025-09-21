"""
座標相關工具函數
"""
from typing import List

from django.contrib.gis.geos import Point


class CoordinateDistanceCalculator:
    """座標距離計算器 - 計算座標點間的距離"""

    @staticmethod
    def calculate_distance(start: List[float], end: List[float]) -> float:
        """計算兩點間直線距離（米）- 使用PostGIS Point

        Args:
            start: [lng, lat] 起點座標
            end: [lng, lat] 終點座標

        Returns:
            距離（米）
        """
        point1 = Point(start[0], start[1], srid=4326)
        point2 = Point(end[0], end[1], srid=4326)

        # 使用 GeoDjango 的距離計算
        point1_projected = point1.transform(3857, clone=True)  # Web Mercator
        point2_projected = point2.transform(3857, clone=True)

        return point1_projected.distance(point2_projected)  # 返回米

    @staticmethod
    def calculate_total_distance(coordinates: List[List[float]]) -> float:
        """計算軌跡總距離

        Args:
            coordinates: [[lng, lat], [lng, lat], ...] 座標序列

        Returns:
            總距離（米）
        """
        total_distance = 0
        for i in range(len(coordinates) - 1):
            total_distance += CoordinateDistanceCalculator.calculate_distance(
                coordinates[i], coordinates[i + 1]
            )
        return total_distance
