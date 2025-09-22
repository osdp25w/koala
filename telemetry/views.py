from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import SearchFilter
from rest_framework.pagination import LimitOffsetPagination

from account.simple_permissions import IsAdmin, IsStaff
from telemetry.filters import TelemetryDeviceFilter
from telemetry.models import TelemetryDevice
from telemetry.serializers import (
    TelemetryDeviceCreateSerializer,
    TelemetryDeviceSerializer,
    TelemetryDeviceUpdateSerializer,
)
from utils.constants import ViewSetAction
from utils.response import APIFailedResponse, APISuccessResponse
from utils.views import BaseGenericViewSet


class TelemetryDeviceViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    queryset = TelemetryDevice.objects.select_related('bike').all()
    serializer_class = TelemetryDeviceSerializer
    permission_classes = [IsStaff | IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TelemetryDeviceFilter
    pagination_class = LimitOffsetPagination

    def get_serializer_class(self):
        match self.action:
            case ViewSetAction.CREATE:
                return TelemetryDeviceCreateSerializer
            case ViewSetAction.UPDATE | ViewSetAction.PARTIAL_UPDATE:
                return TelemetryDeviceUpdateSerializer
            case _:
                return TelemetryDeviceSerializer

    def perform_destroy(self, instance):
        # 檢查是否有綁定的腳踏車
        if hasattr(instance, 'bike') and instance.bike:
            raise serializers.ValidationError(
                {
                    'bike_association': f'Cannot delete device that is associated with bike {instance.bike.bike_id}. Please remove bike association first.'
                }
            )
        instance.delete()


@api_view(['GET'])
@permission_classes([IsStaff | IsAdmin])
def telemetry_device_status_options_view(request):
    """獲取所有 TelemetryDevice status 選項"""
    status_options = [
        {'value': choice[0], 'label': choice[1]}
        for choice in TelemetryDevice.StatusOptions.choices
    ]
    return APISuccessResponse(data={'status_options': status_options})
