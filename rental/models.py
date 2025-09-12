from decimal import Decimal

from django.db import models

from account.models import Member
from bike.models import BikeInfo


class BikeRental(models.Model):
    class RentalStatusOptions(models.TextChoices):
        RESERVED = ('reserved', 'Reserved')
        ACTIVE = ('active', 'Active')
        COMPLETED = ('completed', 'Completed')
        CANCELLED = ('cancelled', 'Cancelled')

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name='bike_rentals'
    )
    bike = models.ForeignKey(BikeInfo, on_delete=models.CASCADE, related_name='rentals')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    rental_status = models.CharField(
        max_length=20,
        choices=RentalStatusOptions.choices,
        default=RentalStatusOptions.ACTIVE,
    )

    pickup_location = models.CharField(max_length=200, blank=True, default='')
    return_location = models.CharField(max_length=200, blank=True, default='')
    total_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    memo = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['member', 'start_time']),
            models.Index(fields=['bike', 'start_time']),
            models.Index(fields=['rental_status']),
            models.Index(fields=['start_time']),
            models.Index(fields=['end_time']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.member.username} - {self.bike.bike_id} - {self.get_rental_status_display()}"

    def get_duration_minutes(self):
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time).total_seconds() / 60)
        return None
