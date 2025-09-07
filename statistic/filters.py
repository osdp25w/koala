from django_filters import rest_framework as filters

from statistic.models import DailyOverviewStatistics, HourlyOverviewStatistics


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
