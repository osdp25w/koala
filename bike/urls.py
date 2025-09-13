from django.urls import include, path
from rest_framework.routers import DefaultRouter

from bike.views import (
    BikeCategoryViewSet,
    BikeErrorLogStatusViewSet,
    BikeInfoViewSet,
    BikeRealtimeStatusViewSet,
    BikeSeriesViewSet,
    bike_status_options_view,
)

app_name = 'bike'

router = DefaultRouter()
router.register(r'categories', BikeCategoryViewSet, basename='categories')
router.register(r'series', BikeSeriesViewSet, basename='series')
router.register(r'bikes', BikeInfoViewSet, basename='bikes')
router.register(
    r'realtime-status', BikeRealtimeStatusViewSet, basename='realtime-status'
)
router.register(
    r'error-log-status', BikeErrorLogStatusViewSet, basename='error-log-status'
)

urlpatterns = [
    path('', include(router.urls)),
    path('status-options/', bike_status_options_view, name='status-options'),
]
