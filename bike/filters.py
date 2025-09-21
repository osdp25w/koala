import django_filters

from bike.models import BikeErrorLog, BikeErrorLogStatus, BikeRealtimeStatus


class BikeErrorLogStatusFilter(django_filters.FilterSet):
    is_read = django_filters.BooleanFilter()
    level = django_filters.ChoiceFilter(
        field_name='error_log__level', choices=BikeErrorLog.LevelOptions.choices
    )

    class Meta:
        model = BikeErrorLogStatus
        fields = ['is_read', 'level']


class BikeRealtimeStatusFilter(django_filters.FilterSet):
    bike_id_q = django_filters.CharFilter(
        field_name='bike__bike_id', lookup_expr='icontains'
    )
    bike_name_q = django_filters.CharFilter(
        field_name='bike__bike_name', lookup_expr='icontains'
    )
    bike_model_q = django_filters.CharFilter(
        field_name='bike__bike_model', lookup_expr='icontains'
    )

    class Meta:
        model = BikeRealtimeStatus
        fields = ['bike__bike_id', 'bike__bike_name', 'bike__bike_model']
