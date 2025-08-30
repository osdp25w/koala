"""
Debug tools for RBAC system

These functions are for debugging and development purposes only.
Not intended for production use.
"""

from account.caches import PermissionCache
from utils.constants import RowAccessLevel


def show_model_permissions(profile, model_class):
    actions = ['get', 'create', 'update', 'delete', 'export']
    model_name = model_class._meta.model_name

    print(f"\n=== {profile.username} 對 {model_name} 的權限 ===")

    for action in actions:
        print(f"\n--- {action.upper()} 權限 ---")

        # 獲取該action的欄位權限
        field_access = PermissionCache.get_allowed_fields_with_access(
            profile, model_class, action
        )

        if not field_access:
            print('  無權限')
            continue

        # 按權限級別分組顯示
        by_level = {}
        for field, level in field_access.items():
            level_name = RowAccessLevel.to_string(level)
            if level_name not in by_level:
                by_level[level_name] = []
            by_level[level_name].append(field)

        for level_name, fields in by_level.items():
            print(f"  {level_name.upper()}: {', '.join(sorted(fields))}")


def show_profile_all_permissions(profile):
    """顯示用戶對所有模型的權限"""
    from account.models import Member, Staff

    models = [Member, Staff]

    for model_class in models:
        show_model_permissions(profile, model_class)
        print('\n' + '=' * 60)


def show_rbac_summary(profile):
    """顯示用戶的RBAC角色和權限摘要"""
    print(f"\n=== {profile.username} RBAC 摘要 ===")
    print(f"用戶類型: {profile.__class__.__name__}")
    print(f"Profile Type: {getattr(profile, 'type', 'N/A')}")

    print('\n--- 分配的角色 ---')
    roles = profile.rbac_roles.all()
    if not roles.exists():
        print('  無分配角色')
    else:
        for role in roles:
            print(f"  • {role.name} ({'僅限員工' if role.is_staff_only else '一般用戶'})")

            permissions = role.permissions.all()
            if permissions.exists():
                print(f"    權限數量: {permissions.count()}")
                for perm in permissions:
                    print(f"      - {perm.scope.code}:{perm.action}({perm.row_access})")
            else:
                print('    無權限')


def clear_profile_cache(profile):
    """清除指定用戶的權限快取"""
    PermissionCache.clear_profile_cache(profile)
    print(f"已清除 {profile.username} 的權限快取")


def clear_all_permission_cache():
    """清除所有權限快取"""
    from account.models import Member, Staff

    PermissionCache.clear_model_cache(Member)
    PermissionCache.clear_model_cache(Staff)
    print('已清除所有權限快取')


# 使用示例和快捷方式
def debug_member_permissions():
    """快速 debug Member 權限的示例函數"""
    from account.models import Member

    # 獲取第一個 Member 用於測試
    member = Member.objects.first()
    if not member:
        print('沒有找到 Member 用戶')
        return

    show_profile_all_permissions(member)
    show_rbac_summary(member)


def debug_staff_permissions():
    """快速 debug Staff 權限的示例函數"""
    from account.models import Staff

    # 獲取第一個 Staff 用於測試
    staff = Staff.objects.first()
    if not staff:
        print('沒有找到 Staff 用戶')
        return

    show_model_permissions(staff, Staff)
    show_rbac_summary(staff)
