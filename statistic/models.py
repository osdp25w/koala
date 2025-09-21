import datetime
import re
import uuid

from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import LineString, Point
from django.db import models
from psqlextra.models import PostgresModel, PostgresPartitionedModel
from psqlextra.types import PostgresPartitioningMethod

from account.models import Member
from bike.models import BikeInfo
from rental.models import BikeRental


class RideSession(models.Model):
    class StatusOptions(models.TextChoices):
        CREATED = ('created', 'Created')
        EXTRACTING = ('extracting', 'Extracting')
        ANALYZING = ('analyzing', 'Analyzing')
        COMPLETED = ('completed', 'Completed')
        FAILED = ('failed', 'Failed')

    bike_rental = models.OneToOneField(
        BikeRental, on_delete=models.CASCADE, related_name='ride_session'
    )

    status = models.CharField(
        max_length=20, choices=StatusOptions.choices, default=StatusOptions.CREATED
    )
    raw_point_count = models.IntegerField(default=0)
    valid_point_count = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    # 格式: [{"lat": 25.123456, "lng": 121.567890, "time": "2024-01-01T10:30:00Z"}, ...]
    gps_trajectory = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['bike_rental']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.id} - {self.bike_rental.id} - {self.status}"


class RouteMatchResult(models.Model):
    """
    路線匹配結果 - 記錄每次騎乘的路線匹配詳細資訊
    """

    ride_session = models.OneToOneField(
        RideSession, on_delete=models.CASCADE, related_name='match_result'
    )

    geometry = gis_models.LineStringField(srid=4326)
    start_point = gis_models.PointField(srid=4326)
    end_point = gis_models.PointField(srid=4326)
    distance_meters = models.FloatField()
    average_confidence = models.FloatField(default=1.0)
    fallback_strategy = models.JSONField(default=dict)
    is_sync_geometry_coordinate = models.BooleanField(default=False)
    resync_details = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ride_session']),
            models.Index(fields=['average_confidence']),
            models.Index(fields=['distance_meters']),
            models.Index(fields=['is_sync_geometry_coordinate']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"MatchResult {self.ride_session.id} - {self.distance_meters}m"


class GeometryCoordinate(models.Model):
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    total_usage_count = models.PositiveIntegerField(default=1)
    is_mock = models.BooleanField(default=False)

    point = gis_models.PointField(srid=4326)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['total_usage_count']),
            models.Index(fields=['is_mock']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['latitude', 'longitude']
        ordering = ['-total_usage_count', '-updated_at']

    def save(self, *args, **kwargs):
        """儲存時自動建立PostGIS Point"""
        if not self.point:
            self.point = Point(float(self.longitude), float(self.latitude), srid=4326)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.latitude}, {self.longitude}) - 使用次數: {self.total_usage_count}"


class DailyOverviewStatistics(models.Model):
    online_bikes_count = models.IntegerField(default=0)
    offline_bikes_count = models.IntegerField(default=0)
    total_distance_km = models.FloatField(default=0.0)
    carbon_reduction_kg = models.FloatField(default=0.0)
    average_soc = models.FloatField(null=True, blank=True)
    collected_time = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-collected_time']
        indexes = [
            models.Index(fields=['collected_time']),
        ]

    def __str__(self):
        return f"{self.collected_time} - 上線: {self.online_bikes_count}, 總里程: {self.total_distance_km}km"


class HourlyOverviewStatistics(models.Model):
    online_bikes_count = models.IntegerField(default=0)
    offline_bikes_count = models.IntegerField(default=0)
    average_soc = models.FloatField(null=True, blank=True)
    distance_km = models.FloatField(default=0.0)
    carbon_reduction_kg = models.FloatField(default=0.0)
    collected_time = models.DateTimeField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-collected_time']
        indexes = [
            models.Index(fields=['collected_time']),
        ]

    def __str__(self):
        return f"{self.collected_time} - 上線: {self.online_bikes_count}, 里程: {self.distance_km}km, SOC: {self.average_soc}%"


class HourlyGeometryCoordinateStatistics(models.Model):
    """
    座標小時級別使用統計
    記錄每個座標在特定小時的使用次數
    """

    geometry_coordinate = models.ForeignKey(
        GeometryCoordinate, on_delete=models.CASCADE, related_name='hourly_stats'
    )
    collected_time = models.DateTimeField()  # 精確到小時，例如 2024-01-15 10:00:00
    usage_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['geometry_coordinate', 'collected_time']
        indexes = [
            models.Index(fields=['collected_time']),
            models.Index(fields=['geometry_coordinate', 'collected_time']),
            models.Index(fields=['usage_count']),
        ]
        ordering = ['-collected_time', '-usage_count']

    def __str__(self):
        return f"{self.geometry_coordinate} - {self.collected_time.strftime('%Y-%m-%d %H:00')} - {self.usage_count} 次"


class DailyGeometryCoordinateStatistics(models.Model):
    """
    座標日級別使用統計
    記錄每個座標在特定日期的使用次數
    """

    geometry_coordinate = models.ForeignKey(
        GeometryCoordinate, on_delete=models.CASCADE, related_name='daily_stats'
    )
    collected_time = models.DateField()
    usage_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['geometry_coordinate', 'collected_time']
        indexes = [
            models.Index(fields=['collected_time']),
            models.Index(fields=['geometry_coordinate', 'collected_time']),
            models.Index(fields=['usage_count']),
        ]
        ordering = ['-collected_time', '-usage_count']

    def __str__(self):
        return (
            f"{self.geometry_coordinate} - {self.collected_time} - {self.usage_count} 次"
        )
