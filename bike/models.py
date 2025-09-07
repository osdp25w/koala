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
    STATUS_IDLE = 'idle'
    STATUS_RENTED = 'rented'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_ERROR = 'error'

    STATUS_ONLINE = (STATUS_IDLE, STATUS_RENTED)
    STATUS_OFFLINE = (STATUS_MAINTENANCE, STATUS_ERROR)

    STATUS_OPTIONS = [
        (STATUS_IDLE, 'Idle'),
        (STATUS_RENTED, 'Rented'),
        (STATUS_MAINTENANCE, 'Maintenance'),
        (STATUS_ERROR, 'Error'),
    ]
    bike = models.OneToOneField(
        BikeInfo,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='realtime_status',
    )
    latitude = models.IntegerField(verbose_name='緯度 * 10^6')
    longitude = models.IntegerField(verbose_name='經度 * 10^6')
    battery_level = models.SmallIntegerField()

    status = models.CharField(
        max_length=50,
        choices=STATUS_OPTIONS,
        default=STATUS_IDLE,
    )

    orig_status = models.CharField(
        max_length=50,
        choices=STATUS_OPTIONS,
        null=True,
        blank=True,
    )
    current_member_ids = models.JSONField(
        default=list,
        blank=True,
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

    def get_is_rentable(self):
        """
        判斷車輛是否可出借

        Returns:
            bool: 只有當狀態為 IDLE 時才可出借
        """
        return self.status == self.STATUS_IDLE

    @property
    def lat_decimal(self):
        """回傳十進位緯度"""
        return self.latitude / 1000000.0

    @property
    def lng_decimal(self):
        """回傳十進位經度"""
        return self.longitude / 1000000.0


class BikeErrorLog(models.Model):
    """
    車輛錯誤日誌模型
    記錄車輛相關的各種錯誤和異常狀況
    """

    LEVEL_INFO = 'info'
    LEVEL_WARNING = 'warning'
    LEVEL_CRITICAL = 'critical'

    LEVEL_CHOICES = [
        (LEVEL_INFO, 'Info'),
        (LEVEL_WARNING, 'Warning'),
        (LEVEL_CRITICAL, 'Critical'),
    ]

    code = models.CharField(max_length=50)
    bike = models.ForeignKey(
        BikeInfo,
        on_delete=models.SET_NULL,
        related_name='bike_error_logs',
        null=True,
        blank=True,
    )
    level = models.CharField(
        max_length=20, choices=LEVEL_CHOICES, default=LEVEL_WARNING
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
