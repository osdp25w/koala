from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BikeRealtimeStatusViewSet

app_name = 'bike'

router = DefaultRouter()
router.register(
    r'realtime-status', BikeRealtimeStatusViewSet, basename='realtime-status'
)

urlpatterns = [
    path('', include(router.urls)),
]
