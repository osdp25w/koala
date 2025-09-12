from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from bike.models import BikeInfo, BikeRealtimeStatus


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
