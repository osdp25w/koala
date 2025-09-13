"""
Base test classes for telemetry app tests with fixture loading
"""
from django.test import TestCase
from rest_framework.test import APIClient

from account.models import Member, Staff
from telemetry.models import TelemetryDevice


class BaseTelemetryTestWithFixtures(TestCase):
    """Base test class that loads telemetry fixtures"""

    fixtures = [
        'account/tests/fixtures/users.json',
        'account/tests/fixtures/profiles.json',
        'telemetry/tests/fixtures/telemetry_devices.json',
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        # 載入會員和工作人員
        self.member_profile = Member.objects.get(id=1)
        self.staff_profile = Staff.objects.get(id=1)
        self.admin_profile = Staff.objects.get(id=2)

        # 載入測試設備
        self.device_alpha = TelemetryDevice.objects.get(IMEI='111111111111111')
        self.device_beta = TelemetryDevice.objects.get(IMEI='222222222222222')
        self.device_gamma = TelemetryDevice.objects.get(IMEI='333333333333333')
        self.device_delta = TelemetryDevice.objects.get(IMEI='444444444444444')


class BaseTelemetryAPITest(BaseTelemetryTestWithFixtures):
    """Base API test class with authentication helpers"""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def authenticate_as(self, profile):
        """設置認證"""
        from account.jwt import JWTService

        tokens = JWTService.create_tokens(profile)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")

    def clear_authentication(self):
        """清除認證"""
        self.client.credentials()
