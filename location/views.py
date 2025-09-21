from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Location
from .serializers import LocationSerializer


class LocationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Location.objects.filter(is_active=True)
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
