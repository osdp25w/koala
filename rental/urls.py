from django.urls import include, path
from rest_framework.routers import DefaultRouter

from rental.views import BikeRentalMemberViewSet, BikeRentalStaffViewSet

app_name = 'rental'

# Member 專用 router
member_router = DefaultRouter()
member_router.register('rentals', BikeRentalMemberViewSet, basename='member-rentals')

# Staff 專用 router
staff_router = DefaultRouter()
staff_router.register('rentals', BikeRentalStaffViewSet, basename='staff-rentals')

urlpatterns = [
    path('member/', include(member_router.urls)),
    path('staff/', include(staff_router.urls)),
]
