from rest_framework import mixins, status

from account.mixins.viewset_mixins import RBACViewSetMixin
from account.models import Member
from account.serializers import (
    MemberDetailSerializer,
    MemberItemSerializer,
    MemberListSerializer,
    MemberUpdateSerializer,
)
from utils.constants import ViewSetAction
from utils.response import APISuccessResponse
from utils.views import BaseGenericViewSet


class MemberViewSet(
    RBACViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    BaseGenericViewSet,
):
    RBAC_AUTO_FILTER_FIELDS = True

    queryset = Member.objects.select_related('user').all()

    def get_serializer_class(self):
        match self.action:
            case ViewSetAction.LIST:
                return MemberListSerializer
            case ViewSetAction.RETRIEVE:
                return MemberItemSerializer
            case ViewSetAction.UPDATE | ViewSetAction.PARTIAL_UPDATE:
                return MemberUpdateSerializer
            case _:
                return MemberItemSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            # 構造 MemberListSerializer 期望的資料格式
            list_data = {'members': page, 'total_count': queryset.count()}
            serializer = self.get_serializer(list_data)
            return self.get_paginated_response(serializer.data)

        # 非分頁情況
        list_data = {'members': queryset, 'total_count': queryset.count()}
        serializer = self.get_serializer(list_data)
        return APISuccessResponse(data=serializer.data)
