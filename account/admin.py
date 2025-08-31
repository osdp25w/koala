from collections import defaultdict

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from account.models import (
    Member,
    RBACModelPermissionScope,
    RBACPermission,
    RBACRole,
    Staff,
)


@admin.register(RBACModelPermissionScope)
class RBACModelPermissionScopeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'related_model_name',
        'parent',
        'type',
        'group',
        'is_active',
    )
    list_filter = ('related_model', 'type', 'group', 'is_active', 'created_at')
    search_fields = ('code', 'name', 'group')
    readonly_fields = ('created_at', 'updated_at', 'effective_fields_display')
    ordering = ('related_model', 'type', 'name')

    fieldsets = (
        ('基本資訊', {'fields': ('code', 'name', 'related_model', 'parent')}),
        (
            '欄位設定',
            {
                'fields': (
                    'included_fields',
                    'excluded_fields',
                    'effective_fields_display',
                )
            },
        ),
        ('分類設定', {'fields': ('type', 'group', 'is_active')}),
        ('其他設定', {'fields': ('details',)}),
        ('時間記錄', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def related_model_name(self, obj):
        if obj.related_model:
            return f"{obj.related_model.app_label}.{obj.related_model.model}"
        return '-'

    related_model_name.short_description = '關聯模型'

    def effective_fields_display(self, obj):
        try:
            effective_fields = obj.get_effective_fields()
            if effective_fields:
                fields_html = ', '.join(
                    [f'<code>{field}</code>' for field in sorted(effective_fields)]
                )
                return mark_safe(f'<div style="max-width: 400px;">{fields_html}</div>')
            return '無有效欄位'
        except Exception as e:
            return f"錯誤: {str(e)}"

    effective_fields_display.short_description = '有效欄位'


@admin.register(RBACPermission)
class RBACPermissionAdmin(admin.ModelAdmin):
    list_display = ('scope', 'action', 'row_access', 'description', 'created_at')
    list_filter = (
        'action',
        'row_access',
        'scope__related_model',
        'scope__type',
        'scope__group',
        'created_at',
    )
    search_fields = ('scope__code', 'scope__name', 'action', 'description')
    readonly_fields = ('created_at', 'effective_fields_display')

    fieldsets = (
        ('權限設定', {'fields': ('scope', 'action', 'row_access')}),
        ('權限詳情', {'fields': ('description', 'effective_fields_display')}),
        ('時間記錄', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def effective_fields_display(self, obj):
        try:
            effective_fields = obj.scope.get_effective_fields()
            if effective_fields:
                fields_html = ', '.join(
                    [f'<code>{field}</code>' for field in sorted(effective_fields)]
                )
                return mark_safe(f'<div style="max-width: 400px;">{fields_html}</div>')
            return '無有效欄位'
        except Exception as e:
            return f"錯誤: {str(e)}"

    effective_fields_display.short_description = '有效欄位'


class PermissionInline(admin.TabularInline):
    model = RBACRole.permissions.through
    extra = 0
    verbose_name = '權限'
    verbose_name_plural = '權限'


@admin.register(RBACRole)
class RBACRoleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_staff_only',
        'permissions_count',
        'users_count',
        'created_at',
    )
    list_filter = ('is_staff_only', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'permissions_summary')
    filter_horizontal = ('permissions',)
    inlines = [PermissionInline]

    fieldsets = (
        ('角色資訊', {'fields': ('name', 'is_staff_only')}),
        ('權限設定', {'fields': ('permissions', 'permissions_summary')}),
        ('其他設定', {'fields': ('description',)}),
        ('時間記錄', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def permissions_count(self, obj):
        return obj.permissions.count()

    permissions_count.short_description = '權限數量'

    def users_count(self, obj):
        member_count = obj.member_profiles.count()
        staff_count = obj.staff_profiles.count()
        return f"Member: {member_count}, Staff: {staff_count}"

    users_count.short_description = '用戶數量'

    def permissions_summary(self, obj):
        """獲取角色權限摘要"""
        permissions = obj.permissions.select_related('scope').all()
        if not permissions:
            return '無權限'

        # 按 model 分組
        model_groups = defaultdict(list)
        for perm in permissions:
            model_name = perm.scope.related_model.model
            model_groups[model_name].append(f"{perm.scope.code}:{perm.action}")

        html_parts = []
        for model, perms in model_groups.items():
            perms_str = ', '.join(perms)
            html_parts.append(f"<strong>{model}</strong>: {perms_str}")

        return mark_safe('<br>'.join(html_parts))

    permissions_summary.short_description = '權限摘要'


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'full_name',
        'email',
        'type',
        'is_active',
        'roles_display',
        'created_at',
    )
    list_filter = ('type', 'is_active', 'rbac_roles', 'created_at')
    search_fields = ('username', 'full_name', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'user_link')
    filter_horizontal = ('rbac_roles',)

    fieldsets = (
        ('基本資訊', {'fields': ('user_link', 'username', 'full_name', 'type')}),
        ('聯絡資訊', {'fields': ('phone', 'national_id')}),
        ('權限設定', {'fields': ('rbac_roles', 'is_active')}),
        ('時間記錄', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def email(self, obj):
        return obj.user.email if obj.user else '-'

    email.short_description = 'Email'

    def roles_display(self, obj):
        roles = obj.rbac_roles.all()
        if roles:
            return ', '.join([role.name for role in roles])
        return '-'

    roles_display.short_description = '角色'

    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">查看 User: {}</a>', url, obj.user.username)
        return '-'

    user_link.short_description = 'Django User'


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'type',
        'is_active',
        'roles_display',
        'created_at',
    )
    list_filter = ('type', 'is_active', 'rbac_roles', 'created_at')
    search_fields = ('username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'user_link')
    filter_horizontal = ('rbac_roles',)

    fieldsets = (
        ('基本資訊', {'fields': ('user_link', 'username', 'type')}),
        ('權限設定', {'fields': ('rbac_roles', 'is_active')}),
        ('時間記錄', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def email(self, obj):
        return obj.user.email if obj.user else '-'

    email.short_description = 'Email'

    def roles_display(self, obj):
        roles = obj.rbac_roles.all()
        if roles:
            return ', '.join([role.name for role in roles])
        return '-'

    roles_display.short_description = '角色'

    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">查看 User: {}</a>', url, obj.user.username)
        return '-'

    user_link.short_description = 'Django User'
