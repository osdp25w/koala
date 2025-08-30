import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from account.jwt import JWTService
from account.models import Member, Staff
from account.services import LoginEncryptionService
from utils.constants import ResponseCode

from .base import FIXTURE_DIR, BaseAPITestWithFixtures


class AuthViewTest(BaseAPITestWithFixtures):
    def setUp(self):
        """設置測試數據"""
        super().setUp()

        self.login_url = reverse('account:login')
        self.refresh_url = reverse('account:refresh_token')
        self.logout_url = reverse('account:logout')

    def test_member_login_success(self):
        """測試 Member 登入成功"""
        # 使用加密服務加密密碼
        encrypted_password = LoginEncryptionService.encrypt_data('password123')

        login_data = {'email': 'member1@test.com', 'password': encrypted_password}

        response = self.client.post(self.login_url, login_data)

        data = self.assert_success_response(response)
        self.assertIn('tokens', data)
        self.assertIn('profile', data)
        self.assertIn('access_token', data['tokens'])
        self.assertIn('refresh_token', data['tokens'])
        self.assertEqual(data['profile']['username'], 'testmember1')
        self.assertEqual(data['profile']['profile_type'], 'member')

    def test_staff_login_success(self):
        """測試 Staff 登入成功"""
        # 使用加密服務加密密碼
        encrypted_password = LoginEncryptionService.encrypt_data('password123')

        login_data = {'email': 'staff1@test.com', 'password': encrypted_password}

        response = self.client.post(self.login_url, login_data)

        data = self.assert_success_response(response)
        self.assertIn('tokens', data)
        self.assertIn('profile', data)
        self.assertIn('access_token', data['tokens'])
        self.assertIn('refresh_token', data['tokens'])
        self.assertEqual(data['profile']['username'], 'teststaff1')
        self.assertEqual(data['profile']['profile_type'], 'staff')

    def test_login_invalid_credentials(self):
        """測試無效憑證登入"""
        encrypted_password = LoginEncryptionService.encrypt_data('wrongpassword')

        login_data = {'email': 'member1@test.com', 'password': encrypted_password}

        response = self.client.post(self.login_url, login_data)

        self.assert_error_response(response, ResponseCode.USER_NOT_FOUND)

    def test_login_missing_fields(self):
        """測試缺少欄位的登入請求"""
        login_data = {
            'email': 'member1@test.com'
            # 缺少 password
        }

        response = self.client.post(self.login_url, login_data)

        self.assert_error_response(response, ResponseCode.VALIDATION_ERROR)

    def test_refresh_token_success(self):
        """測試刷新 token 成功"""
        # 先登入獲取 refresh token
        encrypted_password = LoginEncryptionService.encrypt_data('password123')
        login_data = {'email': 'member1@test.com', 'password': encrypted_password}
        login_response = self.client.post(self.login_url, login_data)
        login_data_parsed = self.get_response_data(login_response)
        refresh_token = login_data_parsed['data']['tokens']['refresh_token']

        # 使用 refresh token 獲取新的 access token
        refresh_data = {'refresh_token': refresh_token}

        response = self.client.post(self.refresh_url, refresh_data)

        data = self.assert_success_response(response)
        self.assertIn('tokens', data)
        self.assertIn('access_token', data['tokens'])

    def test_refresh_token_invalid(self):
        """測試無效的 refresh token"""
        refresh_data = {'refresh_token': 'invalid_token'}

        response = self.client.post(self.refresh_url, refresh_data)

        self.assert_error_response(response, ResponseCode.UNAUTHORIZED)

    def test_logout_success(self):
        """測試登出成功"""
        # 先登入
        encrypted_password = LoginEncryptionService.encrypt_data('password123')
        login_data = {'email': 'member1@test.com', 'password': encrypted_password}
        login_response = self.client.post(self.login_url, login_data)
        login_data_parsed = self.get_response_data(login_response)
        access_token = login_data_parsed['data']['tokens']['access_token']
        refresh_token = login_data_parsed['data']['tokens']['refresh_token']

        # 登出
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_data = {'refresh_token': refresh_token}

        response = self.client.post(self.logout_url, logout_data)

        self.assert_success_response(response)


class JWTServiceTest(TestCase):
    fixtures = [f'{FIXTURE_DIR}/users.json', f'{FIXTURE_DIR}/profiles.json']

    def setUp(self):
        """設置測試數據"""
        self.user = User.objects.get(pk=1)
        self.member = Member.objects.get(pk=1)

    def test_generate_tokens(self):
        """測試生成 JWT tokens"""
        tokens = JWTService.create_tokens(self.member)

        self.assertIn('access_token', tokens)
        self.assertIn('refresh_token', tokens)
        self.assertTrue(isinstance(tokens['access_token'], str))
        self.assertTrue(isinstance(tokens['refresh_token'], str))

    def test_verify_access_token(self):
        """測試驗證 access token"""
        tokens = JWTService.create_tokens(self.member)
        access_token = tokens['access_token']

        is_valid, result = JWTService.validate_token(access_token)

        self.assertTrue(is_valid)
        self.assertEqual(result.user.id, self.user.id)

    def test_verify_refresh_token(self):
        """測試驗證 refresh token"""
        tokens = JWTService.create_tokens(self.member)
        refresh_token = tokens['refresh_token']

        new_tokens = JWTService.refresh_access_token(refresh_token)

        self.assertIsNotNone(new_tokens)
        self.assertIn('access_token', new_tokens)
        self.assertTrue(isinstance(new_tokens['access_token'], str))

    def test_refresh_access_token(self):
        """測試刷新 access token"""
        tokens = JWTService.create_tokens(self.member)
        refresh_token = tokens['refresh_token']

        new_tokens = JWTService.refresh_access_token(refresh_token)

        self.assertIsNotNone(new_tokens)
        self.assertIn('access_token', new_tokens)

        # 驗證新的 access token
        is_valid, result = JWTService.validate_token(new_tokens['access_token'])
        self.assertTrue(is_valid)
        self.assertEqual(result.user.id, self.user.id)
