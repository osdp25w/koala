from collections import defaultdict
from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.db.models import Sum
from django.utils import timezone
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.response import Response

from account.simple_permissions import IsAdmin, IsStaff
from statistic.filters import (
    DailyGeometryCoordinateStatisticsFilter,
    DailyOverviewStatisticsFilter,
    HourlyGeometryCoordinateStatisticsFilter,
    HourlyOverviewStatisticsFilter,
    RouteMatchResultFilter,
)
from statistic.models import (
    DailyGeometryCoordinateStatistics,
    DailyOverviewStatistics,
    HourlyGeometryCoordinateStatistics,
    HourlyOverviewStatistics,
    RouteMatchResult,
)
from statistic.pagination import MemberRouteListPagination
from statistic.serializers import (
    AggregatedGeometryCoordinateStatisticsSerializer,
    DailyOverviewStatisticsSerializer,
    HourlyOverviewStatisticsSerializer,
    MemberRouteListSerializer,
)
from statistic.services import DailyStatisticsService, HourlyStatisticsService
from utils.response import APISuccessResponse
from utils.views import BaseGenericViewSet


class DailyOverviewStatisticsViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsStaff | IsAdmin]
    queryset = DailyOverviewStatistics.objects.all().order_by('-collected_time')
    serializer_class = DailyOverviewStatisticsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DailyOverviewStatisticsFilter

    def list(self, request, *args, **kwargs):
        # 獲取過濾後的 queryset
        queryset = self.filter_queryset(self.get_queryset())

        # 檢查今天是否已有統計記錄
        today = timezone.now().date()
        has_today = queryset.filter(collected_time=today).exists()

        # 如果沒有今天的記錄，添加即時計算的結果
        results = list(queryset)

        if not has_today:
            # 即時計算今天的統計（基於已有的小時統計）
            realtime_data = DailyStatisticsService.calculate_realtime_daily_statistics(
                today
            )
            if realtime_data:
                # 創建一個臨時的模型實例（不保存到DB）
                realtime_instance = DailyOverviewStatistics(**realtime_data)
                results.insert(0, realtime_instance)

        serializer = self.get_serializer(results, many=True)
        return APISuccessResponse(data=serializer.data)


class HourlyOverviewStatisticsViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsStaff | IsAdmin]
    queryset = HourlyOverviewStatistics.objects.all().order_by('-collected_time')
    serializer_class = HourlyOverviewStatisticsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HourlyOverviewStatisticsFilter

    def list(self, request, *args, **kwargs):
        # 獲取過濾後的 queryset
        queryset = self.filter_queryset(self.get_queryset())

        # 檢查當前小時是否已有統計記錄
        current_hour = timezone.now().replace(minute=0, second=0, microsecond=0)
        has_current_hour = queryset.filter(collected_time=current_hour).exists()

        # 如果沒有當前小時的記錄，添加即時計算的結果
        results = list(queryset)

        if not has_current_hour:
            # 即時計算當前小時
            realtime_data = (
                HourlyStatisticsService.calculate_realtime_hourly_statistics(
                    current_hour
                )
            )
            if realtime_data:
                # 創建一個臨時的模型實例（不保存到DB）
                realtime_instance = HourlyOverviewStatistics(**realtime_data)
                results.insert(0, realtime_instance)

        serializer = self.get_serializer(results, many=True)
        return APISuccessResponse(data=serializer.data)


class HourlyGeometryCoordinateStatisticsViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsStaff | IsAdmin]
    queryset = HourlyGeometryCoordinateStatistics.objects.all()
    serializer_class = AggregatedGeometryCoordinateStatisticsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = HourlyGeometryCoordinateStatisticsFilter

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        aggregated_queryset = (
            queryset.select_related('geometry_coordinate')
            .values('geometry_coordinate__latitude', 'geometry_coordinate__longitude')
            .annotate(total_usage_count=Sum('usage_count'))
        )

        serializer = self.get_serializer(aggregated_queryset, many=True)
        return APISuccessResponse(data=serializer.data)


class DailyGeometryCoordinateStatisticsViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsStaff | IsAdmin]
    queryset = DailyGeometryCoordinateStatistics.objects.all()
    serializer_class = AggregatedGeometryCoordinateStatisticsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DailyGeometryCoordinateStatisticsFilter

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        aggregated_queryset = (
            queryset.select_related('geometry_coordinate')
            .values('geometry_coordinate__latitude', 'geometry_coordinate__longitude')
            .annotate(total_usage_count=Sum('usage_count'))
        )

        serializer = self.get_serializer(aggregated_queryset, many=True)
        return APISuccessResponse(data=serializer.data)


class RouteMatchResultViewSet(
    mixins.ListModelMixin,
    BaseGenericViewSet,
):
    permission_classes = [IsStaff | IsAdmin]
    queryset = RouteMatchResult.objects.all()
    serializer_class = MemberRouteListSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RouteMatchResultFilter
    pagination_class = MemberRouteListPagination

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('ride_session__bike_rental__member')
            .order_by('-created_at')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        member_routes = defaultdict(list)
        for route_match in queryset:
            member = route_match.ride_session.bike_rental.member
            member_routes[member.id].append(route_match)

        result_data = []
        for member_id, routes in member_routes.items():
            member = routes[0].ride_session.bike_rental.member
            result_data.append({'member': member, 'routes': routes})

        serializer = self.get_serializer(result_data, many=True)
        return APISuccessResponse(data=serializer.data)
