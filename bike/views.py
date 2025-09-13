from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated

from account.models import Member, Staff
from account.simple_permissions import IsAdmin, IsStaff
from bike.models import BikeCategory, BikeInfo, BikeRealtimeStatus, BikeSeries
from bike.serializers import (
    BikeCategorySerializer,
    BikeInfoCreateSerializer,
    BikeInfoSerializer,
    BikeInfoUpdateSerializer,
    BikeRealtimeStatusSerializer,
    BikeSeriesSerializer,
)
from bike.services import BikeManagementService
from utils.constants import ViewSetAction
from utils.response import APISuccessResponse
from utils.views import BaseGenericViewSet


class BikeCategoryViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = BikeCategorySerializer
    queryset = BikeCategory.objects.all()


class BikeSeriesViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = BikeSeriesSerializer
    queryset = BikeSeries.objects.select_related('category')


class BikeInfoViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    queryset = BikeInfo.objects.select_related(
        'series', 'series__category', 'telemetry_device', 'realtime_status'
    )
    permission_classes = [IsStaff | IsAdmin]

    def get_serializer_class(self):
        match self.action:
            case ViewSetAction.CREATE:
                return BikeInfoCreateSerializer
            case ViewSetAction.UPDATE | ViewSetAction.PARTIAL_UPDATE:
                return BikeInfoUpdateSerializer
            case _:
                return BikeInfoSerializer

    def perform_destroy(self, instance):
        BikeManagementService.delete_bike(instance)


class BikeRealtimeStatusViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = BikeRealtimeStatusSerializer
    pagination_class = LimitOffsetPagination
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bike_status_options_view(request):
    status_options = [
        {'value': choice[0], 'label': choice[1]}
        for choice in BikeRealtimeStatus.StatusOptions.choices
    ]

    return APISuccessResponse(data={'status_options': status_options})
