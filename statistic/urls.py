from rest_framework.routers import DefaultRouter

from statistic.views import (
    DailyOverviewStatisticsViewSet,
    HourlyOverviewStatisticsViewSet,
)

router = DefaultRouter()
router.register(
    r'daily-overview',
    DailyOverviewStatisticsViewSet,
    basename='dailyoverviewstatistics',
)
router.register(
    r'hourly-overview',
    HourlyOverviewStatisticsViewSet,
    basename='hourlyoverviewstatistics',
)

urlpatterns = router.urls
