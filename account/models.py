from django.contrib.auth.models import User
from django.db import models

# 突然想到這樣一個user可以同時有member和staff ==


class PermissionModelMixin(models.Model):
    class Meta:
        abstract = True

    @property
    def all_permissions(self):
        # TODO: cache the result
        return self._get_all_permissions()

    def has_permission(self, resource_code, action):
        """檢查是否有特定權限

        Args:
            resource_code: 資源代碼 (str)，如 'user'
            action: 動作 (str)，如 'create'
        """
        return any(
            perm.resource.code == resource_code and perm.action == action
            for perm in self.all_permissions
        )

    def has_resource_permission(self, resource_code):
        """檢查是否對某資源有任何權限

        Args:
            resource_code: 資源代碼 (str)，如 'user'
        """
        return any(perm.resource.code == resource_code for perm in self.all_permissions)

    def _get_all_permissions(self):
        from account.helpers import PermissionHelper

        return PermissionHelper.get_all_permissions(self)


class Resource(models.Model):
    TYPE_INTERNAL = 'internal'
    TYPE_EXTERNAL = 'external'
    TYPE_OPTIONS = [
        (TYPE_INTERNAL, 'Internal'),
        (TYPE_EXTERNAL, 'External'),
    ]

    code = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=50, choices=TYPE_OPTIONS)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.code


class Permission(models.Model):
    ACTION_CREATE = 'create'
    ACTION_READ = 'read'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_EXPORT = 'export'

    ACTION_OPTIONS = [
        (ACTION_CREATE, 'Create'),
        (ACTION_READ, 'Read'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_EXPORT, 'Export'),
    ]

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name='permissions'
    )
    action = models.CharField(max_length=50, choices=ACTION_OPTIONS, db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        unique_together = ['resource', 'action']
        indexes = [
            models.Index(fields=['resource', 'action']),
        ]

    def __str__(self):
        return f"{self.resource.code} {self.action}"


class PermissionSet(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission, related_name='permission_sets', blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name}"


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_staff_only = models.BooleanField(default=False)
    permission_sets = models.ManyToManyField(PermissionSet, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} (is_staff_only: {self.is_staff_only})"


class MemberRoleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_staff_only=False)


class StaffRoleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_staff_only=True)


class MemberRole(Role):
    objects = MemberRoleManager()

    class Meta:
        proxy = True


class StaffRole(Role):
    objects = StaffRoleManager()

    class Meta:
        proxy = True


class Member(PermissionModelMixin, models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member')
    roles = models.ManyToManyField(Role, related_name='members', blank=True)
    direct_permissions = models.ManyToManyField(
        Permission, related_name='members', blank=True
    )

    is_active = models.BooleanField(default=True, db_index=True)

    # add Member's unique column

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username}"


class Staff(PermissionModelMixin, models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff')
    roles = models.ManyToManyField(Role, related_name='staffs', blank=True)
    direct_permissions = models.ManyToManyField(
        Permission, related_name='staffs', blank=True
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # add Staff's unique column

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username}"
