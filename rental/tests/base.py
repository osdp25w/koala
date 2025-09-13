"""
Base test classes for rental app
"""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from account.jwt import JWTService
from account.models import Member, Staff

# Base fixture directory
FIXTURE_DIR = 'rental/tests/fixtures'


class BaseRentalTestWithFixtures(TestCase):
    """基礎測試類，載入 rental 相關 fixtures"""

    fixtures = [
        # Account fixtures
        'account/tests/fixtures/users.json',
        'account/tests/fixtures/profiles.json',
        # Telemetry fixtures
        'telemetry/tests/fixtures/telemetry_device.json',
        # Bike fixtures
        'bike/tests/fixtures/bike_category.json',
        'bike/tests/fixtures/bike_series.json',
        'bike/tests/fixtures/bike_info.json',
        'bike/tests/fixtures/bike_realtime_status.json',
        # Rental fixtures
        f'{FIXTURE_DIR}/bike_rentals.json',
    ]

    def setUp(self):
        """設置共用的測試數據"""
        # Import models here to avoid circular imports
        from bike.models import BikeCategory, BikeInfo, BikeRealtimeStatus, BikeSeries
        from rental.models import BikeRental
        from telemetry.models import TelemetryDevice

        # Create minimal test users if fixtures don't exist
        try:
            self.member_user1 = User.objects.get(pk=1)
            self.member_user2 = User.objects.get(pk=2)
            self.staff_user1 = User.objects.get(pk=3)
            self.admin_user1 = User.objects.get(pk=4)
            self.member1 = Member.objects.get(pk=1)
            self.member2 = Member.objects.get(pk=2)
            self.staff1 = Staff.objects.get(pk=1)
            self.admin1 = Staff.objects.get(pk=2)
        except (User.DoesNotExist, Member.DoesNotExist, Staff.DoesNotExist):
            self.member_user1 = User.objects.create_user(
                username='member1', email='member1@test.com', password='password123'
            )
            self.member_user2 = User.objects.create_user(
                username='member2', email='member2@test.com', password='password123'
            )
            self.staff_user1 = User.objects.create_user(
                username='staff1', email='staff1@test.com', password='password123'
            )
            self.admin_user1 = User.objects.create_user(
                username='admin1', email='admin1@test.com', password='password123'
            )
            self.member1 = Member.objects.create(
                user=self.member_user1, username='member1'
            )
            self.member2 = Member.objects.create(
                user=self.member_user2, username='member2'
            )
            self.staff1 = Staff.objects.create(
                user=self.staff_user1, username='staff1', is_admin=False
            )
            self.admin1 = Staff.objects.create(
                user=self.admin_user1, username='admin1', is_admin=True
            )

        # Load test data from fixtures
        self.category_electric = BikeCategory.objects.get(pk=1)
        self.series_urban_pro = BikeSeries.objects.get(pk=1)
        self.bike_test001 = BikeInfo.objects.get(pk='TEST001')
        self.bike_test002 = BikeInfo.objects.get(pk='TEST002')
        self.bike_test003 = BikeInfo.objects.get(pk='TEST003')

        self.bike_status_001 = BikeRealtimeStatus.objects.get(bike=self.bike_test001)
        self.bike_status_002 = BikeRealtimeStatus.objects.get(bike=self.bike_test002)
        self.bike_status_003 = BikeRealtimeStatus.objects.get(bike=self.bike_test003)

        self.device_alpha = TelemetryDevice.objects.get(pk='123456789012345')

        # Rental data
        self.active_rental = BikeRental.objects.get(pk=1)
        self.completed_rental = BikeRental.objects.get(pk=2)
        self.old_completed_rental = BikeRental.objects.get(pk=3)
        self.cancelled_rental = BikeRental.objects.get(pk=4)


class BaseRentalAPITest(APITestCase):
    """API 測試基礎類，不依賴複雜 fixtures"""

    def setUp(self):
        self.client = APIClient()

        # Create test users
        self.member_user = User.objects.create_user(
            username='member', email='member@test.com', password='password123'
        )
        self.staff_user = User.objects.create_user(
            username='staff', email='staff@test.com', password='password123'
        )
        self.admin_user = User.objects.create_user(
            username='admin', email='admin@test.com', password='password123'
        )

        self.member_profile = Member.objects.create(
            user=self.member_user, username='member'
        )
        self.staff_profile = Staff.objects.create(
            user=self.staff_user, username='staff', is_admin=False
        )
        self.admin_profile = Staff.objects.create(
            user=self.admin_user, username='admin', is_admin=True
        )

    def authenticate_as(self, profile):
        """設置用戶認證"""
        tokens = JWTService.create_tokens(profile)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
