from django.db import models
from psqlextra.models import PostgresPartitionedModel
from psqlextra.types import PostgresPartitioningMethod


class TelemetryDevice(models.Model):
    IMEI = models.CharField(max_length=20, primary_key=True, verbose_name='設備ID (IMEI)')
    name = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['model']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"{self.IMEI} - {self.name}"


class TelemetryRecord(PostgresPartitionedModel):
    telemetry_device_imei = models.CharField(max_length=20, verbose_name='設備IMEI')
    bike_id = models.CharField(max_length=50, verbose_name='車輛ID')
    sequence_id = models.IntegerField()

    # 時間資訊
    gps_time = models.DateTimeField(verbose_name='GPS時間 (GT)')
    rtc_time = models.DateTimeField(verbose_name='RTC時間 (RT)')
    send_time = models.DateTimeField(verbose_name='發送時間 (ST)')

    # GPS 位置資訊
    longitude = models.IntegerField(verbose_name='經度 (LG) * 10^6')
    latitude = models.IntegerField(verbose_name='緯度 (LA) * 10^6')
    heading_direction = models.SmallIntegerField(verbose_name='方向 (HD) 0-365度')
    vehicle_speed = models.SmallIntegerField(verbose_name='車速 (VS) km/hr')
    altitude = models.IntegerField(verbose_name='海拔 (AT) 公尺')
    gps_hdop = models.SmallIntegerField(verbose_name='GPS HDOP (HP) * 10')
    gps_vdop = models.SmallIntegerField(verbose_name='GPS VDOP (VP) * 10')
    satellites_count = models.SmallIntegerField(verbose_name='衛星數量 (SA)')

    # 電池與動力資訊
    battery_voltage = models.SmallIntegerField(verbose_name='電池電壓 (MV) * 10')
    soc = models.SmallIntegerField(verbose_name='電量百分比 (SO)')
    bike_odometer = models.IntegerField(verbose_name='車輛里程 (EO) 公尺')
    assist_level = models.SmallIntegerField(verbose_name='助力等級 (AL) 0-4')
    pedal_torque = models.IntegerField(verbose_name='踏板扭力 (PT) * 100')
    controller_temp = models.IntegerField(
        null=True, blank=True, verbose_name='控制器溫度 (CT), NULL=未讀'
    )
    pedal_cadence = models.IntegerField(verbose_name='踏板轉速 (CA) * 40')
    battery_temp1 = models.IntegerField(
        null=True, blank=True, verbose_name='電池溫度1 (TP1), NULL=未讀'
    )
    battery_temp2 = models.IntegerField(
        null=True, blank=True, verbose_name='電池溫度2 (TP2), NULL=未讀'
    )

    # 系統狀態資訊
    acc_status = models.BooleanField(verbose_name='ACC狀態 (IN)')
    output_status = models.SmallIntegerField(verbose_name='輸出狀態 (OP)')
    analog_input = models.IntegerField(verbose_name='類比輸入 (AI1) * 1000')
    backup_battery = models.SmallIntegerField(verbose_name='備用電池 (BV) * 10')
    rssi = models.SmallIntegerField(verbose_name='訊號強度 (GQ) 0-31')
    total_odometer = models.IntegerField(verbose_name='總里程 (OD) * 10')
    member_id = models.CharField(max_length=50, blank=True, verbose_name='會員ID (DD)')

    # 報告資訊
    report_id = models.SmallIntegerField(verbose_name='報告類型 (RD)')
    message = models.CharField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='記錄創建時間')
    is_synced = models.BooleanField(default=False, verbose_name='是否已同步處理')

    class PartitioningMeta:
        method = PostgresPartitioningMethod.RANGE
        key = ['created_at']

    class Meta:
        indexes = [
            models.Index(fields=['telemetry_device_imei', 'created_at']),
            models.Index(fields=['bike_id', 'created_at']),
            models.Index(fields=['member_id']),
            models.Index(fields=['gps_time']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['sequence_id']),
            models.Index(fields=['report_id']),
            models.Index(fields=['is_synced']),
            # 新增複合索引提升查詢性能
            models.Index(fields=['telemetry_device_imei', 'sequence_id']),
            models.Index(fields=['bike_id', 'gps_time']),
            models.Index(fields=['is_synced', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.telemetry_device_imei} - {self.bike_id} - {self.created_at}"

    @property
    def lat_decimal(self):
        """回傳十進位緯度"""
        return self.latitude / 1000000.0

    @property
    def lng_decimal(self):
        """回傳十進位經度"""
        return self.longitude / 1000000.0

    @property
    def battery_voltage_decimal(self):
        """回傳十進位電壓"""
        return self.battery_voltage / 10.0
