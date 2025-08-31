from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from account.caches import PermissionCache
from account.models import (
    Member,
    RBACModelPermissionScope,
    RBACPermission,
    RBACRole,
    Staff,
)
from utils.constants import RowAccessLevel

from .base import FIXTURE_DIR


class RBACModelTest(TestCase):
    fixtures = [
        f'{FIXTURE_DIR}/users.json',
        f'{FIXTURE_DIR}/profiles.json',
        f'{FIXTURE_DIR}/rbac_permissions.json',
        f'{FIXTURE_DIR}/rbac_roles.json',
    ]

    def setUp(self):
        """設置測試數據"""
        # 從 fixtures 載入的數據
        self.member1 = Member.objects.get(pk=1)
        self.staff1 = Staff.objects.get(pk=1)
        self.member_scope = RBACModelPermissionScope.objects.get(pk=1)
        self.member_sensitive_scope = RBACModelPermissionScope.objects.get(pk=2)

        # 設置基本關聯用於測試
        member_role = RBACRole.objects.get(pk=1)
        basic_permission = RBACPermission.objects.get(pk=1)
        sensitive_permission = RBACPermission.objects.get(pk=2)

        member_role.permissions.set([basic_permission, sensitive_permission])
        self.member1.rbac_roles.add(member_role)

    def test_rbac_model_permission_scope_creation(self):
        """測試 RBAC 模型權限範圍創建"""
        self.assertEqual(self.member_scope.code, 'member_basic')
        self.assertEqual(self.member_scope.name, 'Member Basic')
        self.assertIn('username', self.member_scope.included_fields)

    def test_rbac_permission_creation(self):
        """測試 RBAC 權限創建"""
        # 從 fixtures 獲取權限
        basic_permission = RBACPermission.objects.get(pk=1)

        self.assertEqual(basic_permission.scope, self.member_scope)
        self.assertEqual(basic_permission.action, RBACPermission.ACTION_GET)
        self.assertEqual(
            basic_permission.row_access, RBACPermission.ROW_ACCESS_PROFILE_HIERARCHY
        )

    def test_rbac_role_permissions(self):
        """測試 RBAC 角色權限分配"""
        # 從 fixtures 獲取角色和權限
        member_role = RBACRole.objects.get(pk=1)
        basic_permission = RBACPermission.objects.get(pk=1)
        sensitive_permission = RBACPermission.objects.get(pk=2)

        self.assertTrue(member_role.permissions.filter(id=basic_permission.id).exists())
        self.assertTrue(
            member_role.permissions.filter(id=sensitive_permission.id).exists()
        )
        self.assertTrue(self.member1.rbac_roles.filter(id=member_role.id).exists())


class RBACPermissionMixinTest(TestCase):
    fixtures = [
        f'{FIXTURE_DIR}/users.json',
        f'{FIXTURE_DIR}/profiles.json',
        f'{FIXTURE_DIR}/rbac_permissions.json',
        f'{FIXTURE_DIR}/rbac_roles.json',
    ]

    def setUp(self):
        """設置測試數據"""
        # 從 fixtures 載入的數據
        self.member = Member.objects.get(pk=1)
        self.scope = RBACModelPermissionScope.objects.get(pk=1)
        self.permission = RBACPermission.objects.get(pk=1)
        self.role = RBACRole.objects.get(pk=1)

        # 設置關聯關係
        self.role.permissions.add(self.permission)
        self.member.rbac_roles.add(self.role)

    def test_has_model_permission(self):
        """測試模型權限檢查"""
        # 清除快取
        PermissionCache.clear_profile_cache(self.member)

        # 測試有權限的情況
        has_permission = self.member.has_model_permission(
            Member, RBACPermission.ACTION_GET
        )
        self.assertTrue(has_permission)

        # 測試沒有權限的情況
        has_permission = self.member.has_model_permission(
            Member, RBACPermission.ACTION_CREATE
        )
        self.assertFalse(has_permission)

    def test_get_allowed_fields(self):
        """測試獲取允許的欄位"""
        # 清除快取
        PermissionCache.clear_profile_cache(self.member)

        allowed_fields = self.member.get_allowed_fields(
            Member, RBACPermission.ACTION_GET
        )

        self.assertIn('id', allowed_fields)
        self.assertIn('username', allowed_fields)
        self.assertIn('email', allowed_fields)


class PermissionCacheTest(TestCase):
    fixtures = [f'{FIXTURE_DIR}/users.json', f'{FIXTURE_DIR}/profiles.json']

    def setUp(self):
        """設置測試數據"""
        self.member = Member.objects.get(pk=1)

    def test_cache_operations(self):
        """測試快取操作"""
        # 測試清除用戶快取
        PermissionCache.clear_profile_cache(self.member)

        # 測試清除模型快取
        PermissionCache.clear_model_cache(Member)

        # 這些方法不應該拋出異常
        self.assertTrue(True)
