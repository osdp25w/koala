from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from bike.models import BikeInfo, BikeRealtimeStatus
from telemetry.models import TelemetryDevice


@receiver(post_save, sender=BikeInfo)
def create_bike_realtime_status(sender, instance, created, **kwargs):
    """
    當 BikeInfo 初次建立時，自動建立對應的 BikeRealtimeStatus
    """
    if created:
        BikeRealtimeStatus.objects.create(
            bike=instance,
            latitude=0,
            longitude=0,
            soc=0,
            vehicle_speed=0,
            status=BikeRealtimeStatus.StatusOptions.IDLE,
            last_seen=timezone.now(),
        )


@receiver(post_save, sender=BikeInfo)
def handle_telemetry_device_status(sender, instance, created, **kwargs):
    """
    當 BikeInfo 建立或更新時，自動處理 TelemetryDevice 狀態
    """
    # 如果腳踏車有分配遙測設備，將設備狀態設為 DEPLOYED
    if instance.telemetry_device:
        telemetry_device = instance.telemetry_device
        if telemetry_device.status != TelemetryDevice.StatusOptions.DEPLOYED:
            telemetry_device.status = TelemetryDevice.StatusOptions.DEPLOYED
            telemetry_device.save()


@receiver(pre_save, sender=BikeInfo)
def handle_telemetry_device_release(sender, instance, **kwargs):
    """
    當 BikeInfo 更新前，處理舊的 TelemetryDevice 釋放
    """
    if instance.pk:  # 只處理更新，不處理新建
        try:
            old_bike = BikeInfo.objects.get(pk=instance.pk)

            # 如果舊的遙測設備與新的不同，釋放舊設備
            if (
                old_bike.telemetry_device
                and old_bike.telemetry_device != instance.telemetry_device
            ):
                old_device = old_bike.telemetry_device
                old_device.status = TelemetryDevice.StatusOptions.AVAILABLE
                old_device.save()

        except BikeInfo.DoesNotExist:
            pass
