import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from rental.models import BikeRental
from statistic.models import RideSession
from statistic.tasks import extract_ride_trajectory

logger = logging.getLogger(__name__)


@receiver(post_save, sender=BikeRental)
def create_ride_session(sender, instance, created, **kwargs):
    """
    BikeRental 建立時自動建立對應的 RideSession
    """
    if created:
        try:
            ride_session = RideSession.objects.create(
                bike_rental=instance, status=RideSession.StatusOptions.CREATED
            )
            logger.info(
                f"Created RideSession {ride_session.id} for BikeRental {instance.id}"
            )
        except Exception as e:
            logger.error(
                f"Error creating RideSession for BikeRental {instance.id}: {e}"
            )


@receiver(post_save, sender=BikeRental)
def handle_rental_completion(sender, instance, **kwargs):
    """
    BikeRental 狀態變更為 completed 時觸發軌跡處理
    """
    if instance.rental_status == BikeRental.RentalStatusOptions.COMPLETED:
        try:
            # 確保有對應的 RideSession
            if hasattr(instance, 'ride_session'):
                ride_session = instance.ride_session

                # 檢查是否已經處理過，避免重複觸發
                if ride_session.status == RideSession.StatusOptions.CREATED:
                    extract_ride_trajectory.delay(instance.id)
                    logger.info(
                        f"Triggered trajectory extraction for BikeRental {instance.id}"
                    )
                else:
                    logger.info(
                        f"RideSession {ride_session.id} already processed (status: {ride_session.status})"
                    )
            else:
                logger.warning(
                    f"No RideSession found for completed BikeRental {instance.id}"
                )
        except Exception as e:
            logger.error(
                f"Error triggering trajectory extraction for BikeRental {instance.id}: {e}"
            )
