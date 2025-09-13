import django_filters

from bike.models import BikeErrorLog, BikeErrorLogStatus


class BikeErrorLogStatusFilter(django_filters.FilterSet):
    is_read = django_filters.BooleanFilter()
    level = django_filters.ChoiceFilter(
        field_name='error_log__level', choices=BikeErrorLog.LevelOptions.choices
    )

    class Meta:
        model = BikeErrorLogStatus
        fields = ['is_read', 'level']
