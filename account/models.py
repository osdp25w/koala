from typing import Optional, Set, Union

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models

from account.mixins.model_mixins import RBACPermissionModelMixin
from account.services import RBACModelPermissionScopeModelService
from utils.encryption import encrypted_fields


class RBACModelPermissionScope(models.Model):
    MODEL_SERVICE_CLASS = RBACModelPermissionScopeModelService

    TYPE_BASE = 'base'
    TYPE_EXTENSION = 'extension'

    TYPE_OPTIONS = [
        (TYPE_BASE, 'Base'),
        (TYPE_EXTENSION, 'Extension'),
    ]

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    related_model = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )
    included_fields = models.JSONField(default=list, blank=True)
    excluded_fields = models.JSONField(default=list, blank=True)
    type = models.CharField(max_length=50, choices=TYPE_OPTIONS)
    group = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['related_model', 'name']),
            models.Index(fields=['parent']),
            models.Index(fields=['type']),
            models.Index(fields=['group']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['related_model', 'type', 'name']

    @property
    def inheritance_depth(self) -> int:
        """獲取繼承深度"""
        return self.MODEL_SERVICE_CLASS.get_inheritance_depth(self)

    def clean(self):
        super().clean()
        self.MODEL_SERVICE_CLASS.validate_scope(self)

    def get_ancestors(self):
        return self.MODEL_SERVICE_CLASS.get_ancestors(self)

    def get_inheritance_chain(self):
        return self.MODEL_SERVICE_CLASS.get_inheritance_chain(self)

    def get_effective_fields(self) -> Set[str]:
        """計算有效欄位：繼承父欄位 + 自己的欄位 - 排除欄位"""
        return self.MODEL_SERVICE_CLASS.get_effective_fields(self)

    def trace_field_source(self, field_name: str) -> str:
        """追蹤欄位來源"""
        return self.MODEL_SERVICE_CLASS.trace_field_source(self, field_name)

    def get_children_recursive(self):
        """獲取所有子孫 scope"""
        return self.MODEL_SERVICE_CLASS.get_children_recursive(self)

    def __str__(self):
        if self.parent:
            return f"{self.code} (extends {self.parent.code})"
        return f"{self.code}"


class RBACPermission(models.Model):
    ACTION_CREATE = 'create'
    ACTION_GET = 'get'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_EXPORT = 'export'

    ACTION_OPTIONS = [
        (ACTION_CREATE, 'Create'),
        (ACTION_GET, 'Get'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_EXPORT, 'Export'),
    ]

    ROW_ACCESS_ALL = 'all'
    ROW_ACCESS_PROFILE_HIERARCHY = 'profile_hierarchy'
    ROW_ACCESS_OWN = 'own'

    ROW_ACCESS_OPTIONS = [
        (ROW_ACCESS_ALL, 'All'),
        (ROW_ACCESS_PROFILE_HIERARCHY, 'Profile Hierarchy'),
        (ROW_ACCESS_OWN, 'Own'),
    ]

    scope = models.ForeignKey(
        RBACModelPermissionScope,
        on_delete=models.CASCADE,
        related_name='rbac_permissions',
    )
    action = models.CharField(max_length=50, choices=ACTION_OPTIONS, db_index=True)
    row_access = models.CharField(
        max_length=50, choices=ROW_ACCESS_OPTIONS, default=ROW_ACCESS_ALL, db_index=True
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['scope', 'action', 'row_access']
        indexes = [
            models.Index(fields=['scope', 'action']),
            models.Index(fields=['row_access']),
        ]

    def __str__(self):
        return f"{self.scope.code}:{self.action}({self.row_access})"


class RBACRole(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_staff_only = models.BooleanField(default=True)
    permissions = models.ManyToManyField(
        RBACPermission, related_name='rbac_roles', blank=True
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} (staff_only: {self.is_staff_only})"


class MemberRBACRoleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_staff_only=False)


class StaffRBACRoleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_staff_only=True)


class MemberRBACRole(RBACRole):
    objects = MemberRBACRoleManager()

    class Meta:
        proxy = True


class StaffRBACRole(RBACRole):
    objects = StaffRBACRoleManager()

    class Meta:
        proxy = True


class UserProfile(RBACPermissionModelMixin, models.Model):
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(max_length=254, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['created_at']

    def __str__(self):
        return f"{self.username}: {self.email}"


@encrypted_fields('national_id')
class Member(UserProfile):
    TYPE_TOURIST = 'tourist'
    TYPE_REAL = 'real'
    TYPE_OPTIONS = [
        (TYPE_TOURIST, 'Tourist'),
        (TYPE_REAL, 'Real'),
    ]

    TYPE_HIERARCHY = {
        TYPE_TOURIST: 1,
        TYPE_REAL: 2,
    }

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='member_profile'
    )
    rbac_roles = models.ManyToManyField(
        RBACRole, related_name='member_profiles', blank=True
    )
    type = models.CharField(max_length=50, choices=TYPE_OPTIONS, default=TYPE_TOURIST)
    full_name = models.CharField(max_length=100, blank=True)
    phone = models.TextField(blank=True)
    _national_id = models.TextField(blank=True, db_column='national_id')

    def clean(self):
        super().clean()
        # 檢查 Member 不能分配到 staff_only 的角色
        if self.pk:  # 只在更新時檢查，避免創建時的問題
            staff_only_roles = self.rbac_roles.filter(is_staff_only=True)
            if staff_only_roles.exists():
                from django.core.exceptions import ValidationError

                role_names = ', '.join(staff_only_roles.values_list('name', flat=True))
                raise ValidationError(f'Member 不能分配到僅限員工的角色: {role_names}')


class Staff(UserProfile):
    TYPE_STAFF = 'staff'
    TYPE_ADMIN = 'admin'
    TYPE_OPTIONS = [
        (TYPE_STAFF, 'Staff'),
        (TYPE_ADMIN, 'Admin'),
    ]

    TYPE_HIERARCHY = {
        TYPE_STAFF: 1,
        TYPE_ADMIN: 2,
    }

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff_profile'
    )
    rbac_roles = models.ManyToManyField(
        RBACRole, related_name='staff_profiles', blank=True
    )
    type = models.CharField(max_length=50, choices=TYPE_OPTIONS, default=TYPE_STAFF)
    # add Staff's unique column


# Add User profile navigation property
def get_user_profile(self) -> Optional[Union['Member', 'Staff']]:
    if hasattr(self, 'member_profile'):
        return self.member_profile
    elif hasattr(self, 'staff_profile'):
        return self.staff_profile
    return None


User.add_to_class('profile', property(get_user_profile))
