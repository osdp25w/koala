from django.urls import include, path
from rest_framework.routers import DefaultRouter

from account import views

app_name = 'account'

router = DefaultRouter()
router.register('members', views.MemberViewSet, basename='member')
router.register('staff', views.StaffViewSet, basename='staff')
router.register(
    'register', views.MemberRegistrationViewSet, basename='member-registration'
)

urlpatterns = [
    # Auth endpoints
    path('auth/login/', views.login_view, name='login'),
    path('auth/refresh/', views.refresh_token_view, name='refresh_token'),
    path('auth/logout/', views.logout_view, name='logout'),
    # ViewSet endpoints
    path('', include(router.urls)),
]
