from rest_framework.routers import DefaultRouter

from statistic.views import (
    DailyGeometryCoordinateStatisticsViewSet,
    DailyOverviewStatisticsViewSet,
    HourlyGeometryCoordinateStatisticsViewSet,
    HourlyOverviewStatisticsViewSet,
    RouteMatchResultViewSet,
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
router.register(
    r'history/hourly-geometry-coordinate',
    HourlyGeometryCoordinateStatisticsViewSet,
    basename='hourlygeometrycoordinatestatistics',
)
router.register(
    r'history/daily-geometry-coordinate',
    DailyGeometryCoordinateStatisticsViewSet,
    basename='dailygeometrycoordinatestatistics',
)
router.register(
    r'routes',
    RouteMatchResultViewSet,
    basename='routematchresult',
)

urlpatterns = router.urls
