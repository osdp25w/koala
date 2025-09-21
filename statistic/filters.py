from django_filters import rest_framework as filters

from statistic.models import (
    DailyGeometryCoordinateStatistics,
    DailyOverviewStatistics,
    HourlyGeometryCoordinateStatistics,
    HourlyOverviewStatistics,
    RouteMatchResult,
)


class DailyOverviewStatisticsFilter(filters.FilterSet):
    collected_time = filters.DateFilter()
    collected_time__gte = filters.DateFilter(
        field_name='collected_time', lookup_expr='gte'
    )
    collected_time__lte = filters.DateFilter(
        field_name='collected_time', lookup_expr='lte'
    )

    class Meta:
        model = DailyOverviewStatistics
        fields = ['collected_time']


class HourlyOverviewStatisticsFilter(filters.FilterSet):
    collected_time = filters.DateTimeFilter()
    collected_time__date = filters.DateFilter(
        field_name='collected_time', lookup_expr='date'
    )
    collected_time__gte = filters.DateTimeFilter(
        field_name='collected_time', lookup_expr='gte'
    )
    collected_time__lte = filters.DateTimeFilter(
        field_name='collected_time', lookup_expr='lte'
    )

    class Meta:
        model = HourlyOverviewStatistics
        fields = ['collected_time']


class HourlyGeometryCoordinateStatisticsFilter(filters.FilterSet):
    collected_time = filters.DateTimeFilter()
    collected_time__date = filters.DateFilter(
        field_name='collected_time', lookup_expr='date'
    )
    collected_time__gte = filters.DateTimeFilter(
        field_name='collected_time', lookup_expr='gte'
    )
    collected_time__lte = filters.DateTimeFilter(
        field_name='collected_time', lookup_expr='lte'
    )

    class Meta:
        model = HourlyGeometryCoordinateStatistics
        fields = ['collected_time']


class DailyGeometryCoordinateStatisticsFilter(filters.FilterSet):
    collected_time = filters.DateFilter()
    collected_time__gte = filters.DateFilter(
        field_name='collected_time', lookup_expr='gte'
    )
    collected_time__lte = filters.DateFilter(
        field_name='collected_time', lookup_expr='lte'
    )

    class Meta:
        model = DailyGeometryCoordinateStatistics
        fields = ['collected_time']


class RouteMatchResultFilter(filters.FilterSet):
    end_time = filters.DateTimeFilter(field_name='ride_session__bike_rental__end_time')
    end_time__date = filters.DateFilter(
        field_name='ride_session__bike_rental__end_time', lookup_expr='date'
    )
    end_time__gte = filters.DateTimeFilter(
        field_name='ride_session__bike_rental__end_time', lookup_expr='gte'
    )
    end_time__lte = filters.DateTimeFilter(
        field_name='ride_session__bike_rental__end_time', lookup_expr='lte'
    )

    class Meta:
        model = RouteMatchResult
        fields = ['end_time']
