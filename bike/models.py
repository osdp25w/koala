from django.db import models

from telemetry.models import TelemetryDevice


class BikeCategory(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['category_name']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.category_name}"


class BikeSeries(models.Model):
    category = models.ForeignKey(
        BikeCategory,
        on_delete=models.CASCADE,
        related_name='bike_series',
    )
    series_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['category', 'series_name']
        indexes = [
            models.Index(fields=['series_name']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['category', 'created_at']

    def __str__(self):
        return f"{self.category.category_name} - {self.series_name}"


class BikeInfo(models.Model):
    bike_id = models.CharField(max_length=50, primary_key=True)
    telemetry_device = models.OneToOneField(
        TelemetryDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bike',
    )
    bike_name = models.CharField(max_length=100)
    bike_model = models.CharField(max_length=100)
    series = models.ForeignKey(
        BikeSeries,
        on_delete=models.CASCADE,
        related_name='bikes',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['series']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.bike_id} - {self.bike_name}"


class BikeRealtimeStatus(models.Model):
    class StatusOptions(models.TextChoices):
        IDLE = ('idle', 'Idle')
        RENTED = ('rented', 'Rented')
        MAINTENANCE = ('maintenance', 'Maintenance')
        ERROR = ('error', 'Error')

    STATUS_ONLINE = (StatusOptions.IDLE, StatusOptions.RENTED)
    STATUS_OFFLINE = (StatusOptions.MAINTENANCE, StatusOptions.ERROR)
    bike = models.OneToOneField(
        BikeInfo,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='realtime_status',
    )
    latitude = models.IntegerField(verbose_name='緯度 * 10^6')
    longitude = models.IntegerField(verbose_name='經度 * 10^6')
    soc = models.SmallIntegerField()
    vehicle_speed = models.SmallIntegerField()

    status = models.CharField(
        max_length=50,
        choices=StatusOptions.choices,
        default=StatusOptions.IDLE,
    )

    orig_status = models.CharField(
        max_length=50,
        choices=StatusOptions.choices,
        null=True,
        blank=True,
    )
    current_member = models.OneToOneField(
        'account.Member',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bike_realtime_status',
    )
    last_seen = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['last_seen']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return f"{self.bike.bike_id} - {self.get_status_display()}"

    def delete(self, using=None, keep_parents=False):
        from django.core.exceptions import ValidationError

        if self.bike:  # 如果還有關聯的 bike
            raise ValidationError(f"無法刪除 bike {self.bike.bike_id} 的即時狀態記錄，請先刪除 bike")
        return super().delete(using=using, keep_parents=keep_parents)

    def save(self, *args, **kwargs):
        # 如果不是新建記錄，且 status 有變更，保存上一個狀態到 orig_status
        if self.pk is not None:  # 不是新建記錄
            try:
                old_instance = BikeRealtimeStatus.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    self.orig_status = old_instance.status
            except BikeRealtimeStatus.DoesNotExist:
                pass  # 如果找不到舊記錄，不處理

        super().save(*args, **kwargs)

    def get_is_rentable(self):
        """
        判斷車輛是否可出借

        Returns:
            bool: 只有當狀態為 IDLE 時才可出借
        """
        return self.status == self.StatusOptions.IDLE

    @property
    def lat_decimal(self):
        """回傳十進位緯度"""
        return self.latitude / 1000000.0

    @property
    def lng_decimal(self):
        """回傳十進位經度"""
        return self.longitude / 1000000.0


class BikeErrorLog(models.Model):
    class LevelOptions(models.TextChoices):
        INFO = ('info', 'Info')
        WARNING = ('warning', 'Warning')
        CRITICAL = ('critical', 'Critical')

    code = models.CharField(max_length=50)
    bike = models.ForeignKey(
        BikeInfo,
        on_delete=models.SET_NULL,
        related_name='bike_error_logs',
        null=True,
        blank=True,
    )
    level = models.CharField(
        max_length=20, choices=LevelOptions.choices, default=LevelOptions.WARNING
    )

    title = models.CharField(max_length=200)
    detail = models.TextField()

    telemetry_device = models.ForeignKey(
        'telemetry.TelemetryDevice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bike_error_logs',
    )
    telemetry_record_snapshot = models.JSONField(null=True, blank=True)
    extra_context = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['bike', 'level']),
            models.Index(fields=['created_at']),
            models.Index(fields=['level']),
            models.Index(fields=['telemetry_device']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.bike.bike_id} - {self.level} - {self.title}"


class BikeErrorLogStatus(models.Model):
    error_log = models.ForeignKey(
        BikeErrorLog, on_delete=models.CASCADE, related_name='read_statuses'
    )
    staff = models.ForeignKey(
        'account.Staff',
        on_delete=models.CASCADE,
        related_name='bike_error_read_statuses',
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['error_log', 'staff']
        indexes = [
            models.Index(fields=['staff', 'is_read']),
            models.Index(fields=['error_log', 'staff']),
        ]

    def __str__(self):
        status = '已讀' if self.is_read else '未讀'
        return f"{self.staff} - {self.error_log.title} ({status})"
