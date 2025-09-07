import datetime

from django.db import models

from account.models import Member
from bike.models import BikeInfo


class LocationStatistics(models.Model):
    latitude = models.IntegerField(verbose_name='緯度 * 10^6')
    longitude = models.IntegerField(verbose_name='經度 * 10^6')
    bike = models.ForeignKey(
        BikeInfo,
        on_delete=models.CASCADE,
        related_name='location_statistics',
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='location_statistics',
    )

    record_count = models.IntegerField(default=1)
    record_time = models.DateTimeField()
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['bike', 'record_time']),
            models.Index(fields=['member', 'record_time']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['record_time']),
            models.Index(fields=['record_count']),
        ]
        unique_together = ['bike', 'member', 'latitude', 'longitude', 'record_time']
        ordering = ['-record_time']

    def __str__(self):
        return f"{self.bike.bike_id} - {self.member.username} - {self.record_time}"

    @property
    def lat_decimal(self):
        """回傳十進位緯度"""
        return self.latitude / 1000000.0

    @property
    def lng_decimal(self):
        """回傳十進位經度"""
        return self.longitude / 1000000.0

    def update_record_count(self):
        """更新記錄次數"""
        self.record_count += 1
        self.save(update_fields=['record_count', 'last_updated'])


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
            models.Index(fields=['created_at']),
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
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.collected_time} - 上線: {self.online_bikes_count}, 里程: {self.distance_km}km, SOC: {self.average_soc}%"
