from django.urls import include, path
from rest_framework.routers import DefaultRouter

from telemetry.views import TelemetryDeviceViewSet, telemetry_device_status_options_view

app_name = 'telemetry'

router = DefaultRouter()
router.register(r'devices', TelemetryDeviceViewSet, basename='devices')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'device-status-options/',
        telemetry_device_status_options_view,
        name='device_status_options',
    ),
]
