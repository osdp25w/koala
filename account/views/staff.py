from rest_framework import mixins, status

from account.mixins.viewset_mixins import RBACViewSetMixin
from account.models import Staff
from account.serializers.staff import (
    StaffDetailSerializer,
    StaffItemSerializer,
    StaffListSerializer,
    StaffUpdateSerializer,
)
from utils.constants import ViewSetAction
from utils.response import APISuccessResponse
from utils.views import BaseGenericViewSet


class StaffViewSet(
    RBACViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    BaseGenericViewSet,
):
    RBAC_AUTO_FILTER_FIELDS = True

    queryset = Staff.objects.select_related('user').all()

    def get_serializer_class(self):
        match self.action:
            case ViewSetAction.LIST:
                return StaffListSerializer
            case ViewSetAction.RETRIEVE:
                return StaffItemSerializer
            case ViewSetAction.UPDATE | ViewSetAction.PARTIAL_UPDATE:
                return StaffUpdateSerializer
            case _:
                return StaffItemSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            list_data = {'staff': page, 'total_count': queryset.count()}
            serializer = self.get_serializer(list_data)
            return self.get_paginated_response(serializer.data)

        # 非分頁情況
        list_data = {'staff': queryset, 'total_count': queryset.count()}
        serializer = self.get_serializer(list_data)
        return APISuccessResponse(data=serializer.data)
