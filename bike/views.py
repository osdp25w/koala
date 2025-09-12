from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated

from account.models import Member, Staff
from bike.models import BikeRealtimeStatus
from bike.serializers import BikeRealtimeStatusSerializer
from utils.views import BaseGenericViewSet


class BikeRealtimeStatusViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = BikeRealtimeStatusSerializer
    ordering = ['-last_seen']

    def get_queryset(self):
        user = self.request.user
        base_queryset = BikeRealtimeStatus.objects.select_related(
            'bike', 'bike__series', 'bike__series__category'
        )

        profile = user.profile

        if isinstance(profile, Staff):
            return base_queryset

        if isinstance(profile, Member):
            return base_queryset.filter(
                Q(status=BikeRealtimeStatus.StatusOptions.IDLE)
                | Q(current_member=profile)
            )

        return base_queryset.none()
