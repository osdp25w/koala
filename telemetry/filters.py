import django_filters

from telemetry.models import TelemetryDevice


class TelemetryDeviceFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=TelemetryDevice.StatusOptions.choices)
    model = django_filters.CharFilter(lookup_expr='icontains')
    IMEI_q = django_filters.CharFilter(field_name='IMEI', lookup_expr='icontains')

    class Meta:
        model = TelemetryDevice
        fields = ['status', 'model', 'IMEI_q']
