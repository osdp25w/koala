from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from account.models import Member, Staff
from account.simple_permissions import IsMember, IsStaff
from rental.filters import BikeRentalFilter
from rental.models import BikeRental
from rental.serializers import (
    BikeRentalDetailSerializer,
    BikeRentalListSerializer,
    BikeRentalMemberCreateSerializer,
    BikeRentalMemberUpdateSerializer,
    BikeRentalStaffCreateSerializer,
    BikeRentalStaffUpdateSerializer,
)
from utils.constants import HTTPMethod, ViewSetAction
from utils.views import BaseGenericViewSet


class BikeRentalMemberViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    BaseGenericViewSet,
):
    """
    Member 租借管理 ViewSet
    - 只能查看和操作自己的租借記錄
    - 支援租借車輛和歸還車輛
    """

    permission_classes = [IsMember]

    def get_queryset(self):
        if not isinstance(self.request.user.profile, Member):
            return BikeRental.objects.none()

        member = self.request.user.profile
        return (
            BikeRental.objects.filter(member=member)
            .select_related('bike', 'bike__series', 'member')
            .order_by('-created_at')
        )

    def get_serializer_class(self):
        match self.action:
            case ViewSetAction.LIST:
                return BikeRentalListSerializer
            case ViewSetAction.RETRIEVE:
                return BikeRentalDetailSerializer
            case ViewSetAction.CREATE:
                return BikeRentalMemberCreateSerializer
            case ViewSetAction.PARTIAL_UPDATE | ViewSetAction.UPDATE:
                return BikeRentalMemberUpdateSerializer
            case _:
                return BikeRentalDetailSerializer

    @action(detail=False, methods=[HTTPMethod.GET])
    def active_rental(self, request):
        member = request.user.profile
        active_rental = (
            BikeRental.objects.filter(
                member=member, rental_status=BikeRental.RentalStatusOptions.ACTIVE
            )
            .select_related('bike', 'bike__series')
            .first()
        )

        if active_rental:
            serializer = BikeRentalDetailSerializer(active_rental)
            return Response(serializer.data)
        else:
            return Response(None)


class BikeRentalStaffViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    BaseGenericViewSet,
):
    """
    Staff 租借管理 ViewSet
    - 可以查看和操作所有租借記錄
    - 可以幫 Member 創建租借
    - 可以強制歸還車輛
    """

    permission_classes = [IsStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_class = BikeRentalFilter
    ordering = ['-created_at']

    def get_queryset(self):
        if not isinstance(self.request.user.profile, Staff):
            return BikeRental.objects.none()

        return BikeRental.objects.select_related(
            'bike', 'bike__series', 'member'
        ).order_by('-created_at')

    def get_serializer_class(self):
        match self.action:
            case ViewSetAction.LIST:
                return BikeRentalListSerializer
            case ViewSetAction.RETRIEVE:
                return BikeRentalDetailSerializer
            case ViewSetAction.CREATE:
                return BikeRentalStaffCreateSerializer
            case ViewSetAction.PARTIAL_UPDATE | ViewSetAction.UPDATE:
                return BikeRentalStaffUpdateSerializer
            case _:
                return BikeRentalDetailSerializer

    @action(detail=False, methods=[HTTPMethod.GET])
    def active_rentals(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            rental_status=BikeRental.RentalStatusOptions.ACTIVE
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = BikeRentalDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = BikeRentalDetailSerializer(queryset, many=True)
        return Response(serializer.data)
