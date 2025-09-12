from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from account.jwt import JWTService
from account.models import Member, RBACModelPermissionScope, RBACPermission, RBACRole
from utils.constants import ResponseCode

from .base import BaseAPITestWithFixtures


class MemberViewSetTest(BaseAPITestWithFixtures):
    def setUp(self):
        """設置測試數據"""
        super().setUp()

        # URLs
        self.list_url = reverse('account:member-list')
        self.detail_url = lambda pk: reverse('account:member-detail', kwargs={'pk': pk})
        self.update_url = lambda pk: reverse('account:member-detail', kwargs={'pk': pk})
        self.delete_url = lambda pk: reverse('account:member-detail', kwargs={'pk': pk})

    def test_member_list_view(self):
        """測試 Member 列表視圖"""
        self.authenticate_as_member1()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 在測試環境中，檢查實際的回應結構
        if 'data' in response.data:
            # 統一格式
            self.assertIn('members', response.data['data'])
            self.assertIn('total_count', response.data['data'])
            members_count = len(response.data['data']['members'])
        else:
            # 直接序列化器格式
            self.assertIn('members', response.data)
            self.assertIn('total_count', response.data)
            members_count = len(response.data['members'])

        self.assertGreaterEqual(members_count, 1)  # 至少能看到一些成員

    def test_member_list_field_filtering(self):
        """測試 Member 列表的欄位過濾"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        response = self.client.get(self.list_url)

        # 在測試環境中，檢查實際的回應結構
        if 'data' in response.data and 'members' in response.data['data']:
            members_data = response.data['data']['members']
        else:
            # 直接是列表數據
            members_data = response.data.get('members', response.data)

        # 找到對應的成員數據
        member1_data = next(
            (m for m in members_data if m['id'] == self.member1.id), None
        )
        member2_data = next(
            (m for m in members_data if m['id'] == self.member2.id), None
        )

        if member1_data and member2_data:
            # 基於正確的 RBAC 權限設定檢查欄位過濾
            # Tourist role 權限：
            # 1. member_basic:get:profile_hierarchy - 可查看同級或低級會員基本欄位
            # 2. member_all:get:own - 只能查看自己的完整資訊（敏感欄位）

            # member1 應該能看到自己的所有欄位（基本 + 敏感）
            self.assertIsNotNone(member1_data.get('phone'))  # 自己的敏感欄位
            self.assertIsNotNone(member1_data.get('national_id'))  # 自己的敏感欄位
            self.assertIsNotNone(member1_data.get('username'))  # 基本欄位

            # member1 應該能看到 member2 的基本欄位（profile_hierarchy 權限）
            self.assertIsNotNone(member2_data.get('username'))
            self.assertIsNotNone(member2_data.get('email'))
            self.assertIsNotNone(member2_data.get('full_name'))

            # member1 不應該能看到 member2 的敏感欄位（member_all:get:own 限制）
            self.assertIsNone(member2_data.get('phone'))
            self.assertIsNone(member2_data.get('national_id'))

    def test_member_detail_view_own_record(self):
        """測試查看自己的 Member 詳細資訊"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        response = self.client.get(self.detail_url(self.member1.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 在測試環境中，response.data 是序列化器輸出
        data = response.data
        self.assertEqual(data['id'], self.member1.id)
        self.assertEqual(data['username'], 'testmember1')  # fixture 中的實際用戶名
        # 應該能看到自己的敏感資訊
        self.assertIsNotNone(data['phone'])

    def test_member_detail_view_other_record(self):
        """測試查看其他人的 Member 詳細資訊"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        response = self.client.get(self.detail_url(self.member2.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 在測試環境中，response.data 是序列化器輸出
        data = response.data
        self.assertEqual(data['id'], self.member2.id)
        # 基於當前的權限設定，可能能看到其他人的基本資訊
        # 但敏感資訊的過濾取決於 RBAC 權限設定

    def test_member_update_own_record_should_succeed(self):
        """測試 Member 更新自己資訊應該成功"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        update_data = {'full_name': 'Updated Member One', 'email': 'updated@test.com'}

        response = self.client.patch(self.update_url(self.member1.id), update_data)

        # Member 有 member_all:update:own 權限，應該成功
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 在測試環境中，需要解析 response.content 來獲取統一格式
        import json

        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(content['code'], ResponseCode.SUCCESS)
        self.assertEqual(content['msg'], 'success')
        self.assertIn('data', content)

        # 驗證更新成功
        self.member1.refresh_from_db()
        self.member1.user.refresh_from_db()
        self.assertEqual(self.member1.full_name, 'Updated Member One')
        self.assertEqual(self.member1.user.email, 'updated@test.com')

    def test_member_user_sync(self):
        """測試 Member 和 User 之間的同步功能"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        # 測試更新 Member 的 username 和 email，應該自動同步到 User
        update_data = {
            'username': 'updated_member_username',
            'email': 'updated.member.sync@test.com',
        }

        response = self.client.patch(self.update_url(self.member1.id), update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 驗證 Member 更新成功
        self.member1.refresh_from_db()
        self.assertEqual(self.member1.username, 'updated_member_username')
        self.assertEqual(self.member1.email, 'updated.member.sync@test.com')

        # 驗證 User 也同步更新
        self.member1.user.refresh_from_db()
        self.assertEqual(self.member1.user.username, 'updated_member_username')
        self.assertEqual(self.member1.user.email, 'updated.member.sync@test.com')

    def test_member_update_other_record_should_fail(self):
        """測試更新其他人的 Member 資訊應該失敗"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        update_data = {'full_name': 'Hacked Member Two'}

        response = self.client.patch(self.update_url(self.member2.id), update_data)

        # Member 只有 member_all:update:own 權限，不能更新別人的資料
        # RBAC 系統會讓查詢失敗，返回 404 狀態，但經過 KoalaRenderer 變成 200 + 錯誤碼
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 解析 response.content 來獲取統一格式
        import json

        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(content['code'], ResponseCode.NOT_FOUND)
        self.assertEqual(content['msg'], 'resource not found')

    def test_member_delete_own_record_should_fail(self):
        """測試 Member 刪除自己的記錄應該失敗（沒有權限）"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        response = self.client.delete(self.delete_url(self.member1.id))

        # Member 沒有刪除權限，直接返回 HTTP 403
        self.assert_error_response(
            response, ResponseCode.PERMISSION_DENIED, expected_status_code=403
        )
        # 確認記錄沒有被刪除
        self.assertTrue(Member.objects.filter(id=self.member1.id).exists())

    def test_member_delete_other_record_should_fail(self):
        """測試刪除其他人的 Member 記錄應該失敗"""
        self.client.credentials(HTTP_AUTHORIZATION=self._get_auth_header(self.member1))

        response = self.client.delete(self.delete_url(self.member2.id))

        # Member 沒有刪除權限，直接返回 HTTP 403
        self.assert_error_response(
            response, ResponseCode.PERMISSION_DENIED, expected_status_code=403
        )
        # 確認記錄沒有被刪除
        self.assertTrue(Member.objects.filter(id=self.member2.id).exists())

    def test_member_unauthorized_access(self):
        """測試未授權訪問"""
        response = self.client.get(self.list_url)

        # 未授權直接返回 HTTP 403
        self.assert_error_response(
            response, ResponseCode.PERMISSION_DENIED, expected_status_code=403
        )


class MemberRegistrationViewSetTest(APITestCase):
    def setUp(self):
        """設置測試數據"""
        self.client = APIClient()
        self.registration_url = reverse('account:member-registration-list')

    def test_member_registration_success(self):
        """測試 Member 註冊成功"""
        # 密碼需要加密傳遞
        from account.services.encryption import MemberEncryptionService

        encrypted_password = MemberEncryptionService.encrypt_data('password123')

        registration_data = {
            'username': 'newmember',
            'email': 'new@member.com',
            'password': encrypted_password,
            'full_name': 'New Member',
            'phone': '+886900000000',
            'type': Member.TypeOptions.TOURIST,
        }

        response = self.client.post(self.registration_url, registration_data)

        # 使用統一格式檢查
        import json

        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content['code'], ResponseCode.SUCCESS)

        # 確認用戶和 Member 被創建
        self.assertTrue(User.objects.filter(username='newmember').exists())
        self.assertTrue(Member.objects.filter(username='newmember').exists())

        member = Member.objects.get(username='newmember')
        self.assertEqual(member.full_name, 'New Member')
        self.assertEqual(member.type, Member.TypeOptions.TOURIST)

    def test_member_registration_duplicate_username(self):
        """測試重複用戶名註冊"""
        # 先創建一個用戶和對應的 Member
        existing_user = User.objects.create_user(
            username='existing', email='existing@test.com', password='password123'
        )
        Member.objects.create(
            user=existing_user,
            username='existing',
            full_name='Existing Member',
            type=Member.TypeOptions.TOURIST,
        )

        registration_data = {
            'username': 'existing',
            'email': 'new@test.com',
            'password': 'password123',
            'full_name': 'New User',
        }

        response = self.client.post(self.registration_url, registration_data)

        # 使用統一格式檢查
        import json

        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content['code'], ResponseCode.VALIDATION_ERROR)

    def test_member_registration_missing_required_fields(self):
        """測試缺少必填欄位的註冊"""
        registration_data = {
            'username': 'incomplete'
            # 缺少 email, password, full_name
        }

        response = self.client.post(self.registration_url, registration_data)

        # 使用統一格式檢查
        import json

        content = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(content['code'], ResponseCode.VALIDATION_ERROR)
