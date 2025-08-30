"""
Base test classes with fixtures
"""
import json
import logging

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from account.jwt import JWTService
from account.models import Member, RBACRole, Staff

# Base fixture directory
FIXTURE_DIR = 'account/tests/fixtures'


class BaseTestWithFixtures(TestCase):
    """基礎測試類，載入標準 fixtures"""

    fixtures = [
        f'{FIXTURE_DIR}/users.json',
        f'{FIXTURE_DIR}/profiles.json',
        f'{FIXTURE_DIR}/rbac_permissions.json',
        f'{FIXTURE_DIR}/rbac_roles.json',
    ]

    def setUp(self):
        """設置共用的測試數據"""
        # Users
        self.member_user1 = User.objects.get(pk=1)
        self.member_user2 = User.objects.get(pk=2)
        self.staff_user1 = User.objects.get(pk=3)
        self.admin_user1 = User.objects.get(pk=4)

        # Profiles
        self.member1 = Member.objects.get(pk=1)
        self.member2 = Member.objects.get(pk=2)
        self.staff1 = Staff.objects.get(pk=1)
        self.admin1 = Staff.objects.get(pk=2)

        # Roles
        self.member_role = RBACRole.objects.get(pk=1)
        self.staff_role = RBACRole.objects.get(pk=2)
        self.admin_role = RBACRole.objects.get(pk=3)

        # 設置測試密碼
        for user in [
            self.member_user1,
            self.member_user2,
            self.staff_user1,
            self.admin_user1,
        ]:
            user.set_password('password123')
            user.save()

        # 設置 RBAC 角色關聯（多對多關係在測試邏輯中設定）
        self._setup_rbac_assignments()

    def _setup_rbac_assignments(self):
        """設置 RBAC 角色和權限關聯"""
        from account.models import RBACPermission

        # 使用實際存在的權限，而不是硬編碼的 pk
        # 根據之前檢查的結果，使用實際的權限設定
        # 獲取 Member 相關權限（對應 tourist_role 權限）
        member_basic_get = RBACPermission.objects.filter(
            scope__code='member_basic', action='get', row_access='profile_hierarchy'
        ).first()
        member_all_get = RBACPermission.objects.filter(
            scope__code='member_all', action='get', row_access='own'
        ).first()
        member_update = RBACPermission.objects.filter(
            scope__code='member_all', action='update', row_access='own'
        ).first()

        # 獲取 Staff 相關權限
        staff_get = RBACPermission.objects.filter(
            scope__code='staff_basic', action='get'
        ).first()
        staff_update = RBACPermission.objects.filter(
            scope__code='staff_basic', action='update', row_access='own'
        ).first()
        staff_delete = RBACPermission.objects.filter(
            scope__code='staff_basic', action='delete'
        ).first()

        # 為角色分配權限（只分配存在的權限）
        member_permissions = [
            p for p in [member_basic_get, member_all_get, member_update] if p
        ]
        staff_permissions = [p for p in [staff_get, staff_update, staff_delete] if p]
        admin_permissions = RBACPermission.objects.all()  # Admin 獲得所有權限

        if member_permissions:
            self.member_role.permissions.set(member_permissions)
        if staff_permissions:
            self.staff_role.permissions.set(staff_permissions)
        if admin_permissions:
            self.admin_role.permissions.set(admin_permissions)

        # 為用戶分配角色
        self.member1.rbac_roles.set([self.member_role])
        self.member2.rbac_roles.set([self.member_role])
        self.staff1.rbac_roles.set([self.staff_role])
        self.admin1.rbac_roles.set([self.admin_role])


class BaseAPITestWithFixtures(APITestCase, BaseTestWithFixtures):
    """API 測試基礎類，包含認證相關方法"""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        # 在測試期間禁用所有 WARNING 級別的日誌
        logging.disable(logging.WARNING)

    def _get_auth_header(self, profile):
        """獲取認證 header"""
        tokens = JWTService.create_tokens(profile)
        return f"Bearer {tokens['access_token']}"

    def authenticate_as(self, profile):
        """設置用戶認證"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(profile))

    def authenticate_as_member1(self):
        """認證為 member1"""
        self.authenticate_as(self.member1)

    def authenticate_as_member2(self):
        """認證為 member2"""
        self.authenticate_as(self.member2)

    def authenticate_as_staff1(self):
        """認證為 staff1"""
        self.authenticate_as(self.staff1)

    def authenticate_as_admin1(self):
        """認證為 admin1"""
        self.authenticate_as(self.admin1)

    def get_response_data(self, response):
        """
        從 response.content 獲取經過 KoalaRenderer 處理的統一格式數據
        在測試中應該使用這個方法而不是直接使用 response.data
        """
        return json.loads(response.content.decode('utf-8'))

    def assert_success_response(self, response, expected_code=None):
        """檢查成功回應格式"""
        from utils.constants import ResponseCode

        self.assertEqual(response.status_code, 200)
        content = self.get_response_data(response)
        self.assertEqual(content['code'], expected_code or ResponseCode.SUCCESS)
        self.assertEqual(content['msg'], 'success')
        self.assertIn('data', content)
        return content['data']

    def assert_error_response(
        self, response, expected_code, expected_msg=None, expected_status_code=200
    ):
        """
        檢查錯誤回應格式

        Args:
            response: HTTP 回應對象
            expected_code: 期望的錯誤碼（如 ResponseCode.PERMISSION_DENIED）
            expected_msg: 期望的錯誤訊息（可選）
            expected_status_code: 期望的 HTTP 狀態碼（默認 200，表示經過 KoalaRenderer）
        """
        self.assertEqual(response.status_code, expected_status_code)

        if expected_status_code == 200:
            # 經過 KoalaRenderer 的統一格式，需要解析 content
            content = self.get_response_data(response)
            self.assertEqual(content['code'], expected_code)
            if expected_msg:
                self.assertEqual(content['msg'], expected_msg)
            return content
        else:
            # 直接返回的 HTTP 錯誤，檢查 response.data
            self.assertEqual(response.data['code'], expected_code)
            if expected_msg:
                self.assertEqual(response.data['msg'], expected_msg)
            return response.data
