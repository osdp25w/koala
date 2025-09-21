from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import models


class Location(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    point = gis_models.PointField(srid=4326)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """儲存時自動建立PostGIS Point"""
        if not self.point:
            self.point = Point(float(self.longitude), float(self.latitude), srid=4326)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
