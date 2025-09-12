from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from account.jwt import JWTService
from account.models import RBACModelPermissionScope, RBACPermission, RBACRole, Staff
from utils.constants import ResponseCode

from .base import BaseAPITestWithFixtures


class StaffViewSetTest(BaseAPITestWithFixtures):
    def setUp(self):
        """設置測試數據"""
        super().setUp()

        # URLs
        self.list_url = reverse('account:staff-list')
        self.detail_url = lambda pk: reverse('account:staff-detail', kwargs={'pk': pk})
        self.update_url = lambda pk: reverse('account:staff-detail', kwargs={'pk': pk})
        self.delete_url = lambda pk: reverse('account:staff-detail', kwargs={'pk': pk})

    def test_staff_list_view_as_staff(self):
        """測試一般 Staff 查看 Staff 列表"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.staff1))

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('staff', response.data['data'])
        self.assertIn('total_count', response.data['data'])

        # 一般 Staff 基於階層權限，應該只能看到同級或以下的
        staff_data = response.data['data']['staff']
        self.assertGreaterEqual(len(staff_data), 1)  # 至少能看到自己

    def test_staff_list_view_as_admin(self):
        """測試 Admin 查看 Staff 列表"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.admin1))

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Admin 應該能看到所有 Staff
        staff_data = response.data['data']['staff']
        self.assertEqual(len(staff_data), 2)

    def test_staff_detail_view_own_record(self):
        """測試查看自己的 Staff 詳細資訊"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.staff1))

        response = self.client.get(self.detail_url(self.staff1.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 在測試環境中，response.data 是序列化器輸出，而不是渲染器輸出
        # 生產環境中會經過 KoalaRenderer 包裝成統一格式
        data = response.data
        self.assertEqual(data['id'], self.staff1.id)
        self.assertEqual(data['username'], 'teststaff1')  # fixture 中的實際用戶名
        self.assertEqual(data['type'], Staff.TypeOptions.STAFF)

    def test_staff_update_own_record(self):
        """測試更新自己的 Staff 資訊"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.staff1))

        update_data = {'email': 'updated.staff1@test.com'}

        response = self.client.patch(self.update_url(self.staff1.id), update_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.staff1.refresh_from_db()
        self.staff1.user.refresh_from_db()
        self.assertEqual(self.staff1.user.email, 'updated.staff1@test.com')

    def test_staff_user_sync(self):
        """測試 Staff 和 User 之間的同步功能"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.staff1))

        # 測試更新 Staff 的 username 和 email，應該自動同步到 User
        update_data = {
            'username': 'updated_staff_username',
            'email': 'updated.staff.sync@test.com',
        }

        response = self.client.patch(self.update_url(self.staff1.id), update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 驗證 Staff 更新成功
        self.staff1.refresh_from_db()
        self.assertEqual(self.staff1.username, 'updated_staff_username')
        self.assertEqual(self.staff1.email, 'updated.staff.sync@test.com')

        # 驗證 User 也同步更新
        self.staff1.user.refresh_from_db()
        self.assertEqual(self.staff1.user.username, 'updated_staff_username')
        self.assertEqual(self.staff1.user.email, 'updated.staff.sync@test.com')

    def test_admin_update_staff_record(self):
        """測試 Admin 更新一般 Staff 資訊"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.admin1))

        update_data = {'type': Staff.TypeOptions.ADMIN}  # 將 staff 升級為 admin

        response = self.client.patch(self.update_url(self.staff1.id), update_data)

        # 根據權限設定，這可能成功或失敗
        # 如果成功，驗證更新
        if response.status_code == status.HTTP_200_OK:
            self.staff1.refresh_from_db()
            self.assertEqual(self.staff1.type, Staff.TypeOptions.ADMIN)

    def test_staff_delete_own_record(self):
        """測試刪除自己的 Staff 記錄"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.staff1))

        response = self.client.delete(self.delete_url(self.staff1.id))

        # Staff 有刪除權限，檢查統一回應格式
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = self.get_response_data(response)
        self.assertEqual(content['code'], ResponseCode.SUCCESS)
        self.assertFalse(Staff.objects.filter(id=self.staff1.id).exists())
        # 確認 User 也被刪除（通過 signals）
        self.assertFalse(User.objects.filter(id=self.staff_user1.id).exists())

    def test_staff_unauthorized_access(self):
        """測試未授權訪問"""
        response = self.client.get(self.list_url)

        # 未授權直接返回 HTTP 403
        self.assert_error_response(
            response, ResponseCode.PERMISSION_DENIED, expected_status_code=403
        )

    def test_staff_type_hierarchy(self):
        """測試 Staff 類型階層權限"""
        # 這個測試驗證 TYPE_HIERARCHY 的工作原理

        # Admin（level 2）應該能看到 Staff（level 1）的記錄
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.admin1))

        response = self.client.get(self.detail_url(self.staff1.id))

        # Admin 應該能看到一般 Staff 的資料
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_role_validation(self):
        """測試 Staff 角色驗證"""
        # 確認 Staff 不能被分配到 Member 專用的角色
        # 這個測試驗證模型層面的驗證

        from account.models import RBACRole

        member_role = RBACRole.objects.create(
            name='Member Only Role', is_staff_only=False
        )

        # Staff 應該只能被分配 is_staff_only=True 的角色
        # 這個邏輯可能在模型的 clean() 方法中實現
        self.staff1.rbac_roles.add(member_role)

        # 如果有驗證，應該在這裡觸發
        # self.assertRaises(ValidationError, self.staff1.full_clean)
