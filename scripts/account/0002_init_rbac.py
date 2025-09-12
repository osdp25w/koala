from django.contrib.contenttypes.models import ContentType

from account.models import (
    Member,
    RBACModelPermissionScope,
    RBACPermission,
    RBACRole,
    Staff,
)
from koala import settings
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        # 獲取 ContentType
        member_ct = ContentType.objects.get_for_model(Member)
        staff_ct = ContentType.objects.get_for_model(Staff)

        # 創建 Scopes
        print('創建 RBACModelPermissionScope...')
        member_basic_scope, created = RBACModelPermissionScope.objects.get_or_create(
            code='member_basic',
            defaults={
                'name': 'Member Basic',
                'related_model': member_ct,
                'included_fields': [
                    'id',
                    'username',
                    'email',
                    'full_name',
                    'type',
                    'is_active',
                    'created_at',
                    'updated_at',
                ],
                'type': RBACModelPermissionScope.TypeOptions.BASE,
            },
        )
        print(f"{'✓ 創建' if created else '○ 已存在'} {member_basic_scope}")

        member_all_scope, created = RBACModelPermissionScope.objects.get_or_create(
            code='member_all',
            defaults={
                'name': 'Member All',
                'related_model': member_ct,
                'parent': member_basic_scope,
                'included_fields': ['phone', 'national_id'],
                'type': RBACModelPermissionScope.TypeOptions.EXTENSION,
            },
        )
        print(f"{'✓ 創建' if created else '○ 已存在'} {member_all_scope}")

        staff_basic_scope, created = RBACModelPermissionScope.objects.get_or_create(
            code='staff_basic',
            defaults={
                'name': 'Staff Basic',
                'related_model': staff_ct,
                'included_fields': [
                    'id',
                    'username',
                    'email',
                    'type',
                    'is_active',
                    'created_at',
                    'updated_at',
                ],
                'type': RBACModelPermissionScope.TypeOptions.BASE,
            },
        )
        print(f"{'✓ 創建' if created else '○ 已存在'} {staff_basic_scope}")

        # 創建 Permissions
        print('\n創建 RBACPermission...')
        permissions_data = [
            # Member basic permissions
            (
                member_basic_scope,
                RBACPermission.ActionOptions.GET,
                RBACPermission.RowAccessOptions.PROFILE_HIERARCHY,
                'Tourist/Real 查看同級或低級會員基本資訊',
            ),
            # Member all permissions
            (
                member_all_scope,
                RBACPermission.ActionOptions.GET,
                RBACPermission.RowAccessOptions.OWN,
                'Tourist/Real 查看自己完整資訊',
            ),
            (
                member_all_scope,
                RBACPermission.ActionOptions.UPDATE,
                RBACPermission.RowAccessOptions.OWN,
                'Tourist/Real 更新自己完整資訊',
            ),
            (
                member_all_scope,
                RBACPermission.ActionOptions.GET,
                RBACPermission.RowAccessOptions.ALL,
                'Staff/Admin 查看所有會員完整資訊',
            ),
            (
                member_all_scope,
                RBACPermission.ActionOptions.CREATE,
                RBACPermission.RowAccessOptions.ALL,
                'Staff/Admin 創建會員完整資料',
            ),
            (
                member_all_scope,
                RBACPermission.ActionOptions.UPDATE,
                RBACPermission.RowAccessOptions.ALL,
                'Staff/Admin 更新所有會員完整資訊',
            ),
            (
                member_all_scope,
                RBACPermission.ActionOptions.DELETE,
                RBACPermission.RowAccessOptions.ALL,
                'Staff/Admin 刪除會員',
            ),
            # Staff permissions
            (
                staff_basic_scope,
                RBACPermission.ActionOptions.UPDATE,
                RBACPermission.RowAccessOptions.OWN,
                'Staff/Admin 更新自己資訊',
            ),
            (
                staff_basic_scope,
                RBACPermission.ActionOptions.GET,
                RBACPermission.RowAccessOptions.PROFILE_HIERARCHY,
                'Staff/Admin 查看同級或低級員工',
            ),
            (
                staff_basic_scope,
                RBACPermission.ActionOptions.GET,
                RBACPermission.RowAccessOptions.ALL,
                'Admin 查看所有員工',
            ),
            (
                staff_basic_scope,
                RBACPermission.ActionOptions.CREATE,
                RBACPermission.RowAccessOptions.ALL,
                'Admin 創建員工',
            ),
            (
                staff_basic_scope,
                RBACPermission.ActionOptions.UPDATE,
                RBACPermission.RowAccessOptions.ALL,
                'Admin 更新員工資訊',
            ),
            (
                staff_basic_scope,
                RBACPermission.ActionOptions.DELETE,
                RBACPermission.RowAccessOptions.ALL,
                'Admin 刪除員工',
            ),
        ]

        created_permissions = {}
        for scope, action, row_access, description in permissions_data:
            perm, created = RBACPermission.objects.get_or_create(
                scope=scope,
                action=action,
                row_access=row_access,
                defaults={'description': description},
            )
            key = f"{scope.code}:{action}:{row_access}"
            created_permissions[key] = perm
            print(f"{'✓ 創建' if created else '○ 已存在'} {perm}")

        # 創建 Roles
        print('\n創建 RBACRole...')

        # Tourist Role (Member)
        tourist_role, created = RBACRole.objects.get_or_create(
            name='tourist_role',
            defaults={'is_staff_only': False, 'description': '觀光客角色'},
        )
        if created:
            tourist_role.permissions.add(
                created_permissions['member_basic:get:profile_hierarchy'],
                created_permissions['member_all:get:own'],
                created_permissions['member_all:update:own'],
            )
        print(f"{'✓ 創建' if created else '○ 已存在'} {tourist_role}")
        print(f"  - 擁有 {tourist_role.permissions.count()} 個權限")

        # Real Member Role (Member)
        real_member_role, created = RBACRole.objects.get_or_create(
            name='real_member_role',
            defaults={'is_staff_only': False, 'description': '真實會員角色'},
        )
        if created:
            real_member_role.permissions.add(
                created_permissions['member_basic:get:profile_hierarchy'],
                created_permissions['member_all:get:own'],
                created_permissions['member_all:update:own'],
            )
        print(f"{'✓ 創建' if created else '○ 已存在'} {real_member_role}")
        print(f"  - 擁有 {real_member_role.permissions.count()} 個權限")

        # Staff Role (Staff)
        staff_role, created = RBACRole.objects.get_or_create(
            name='staff_role', defaults={'is_staff_only': True, 'description': '員工角色'}
        )
        if created:
            staff_role.permissions.add(
                created_permissions['member_all:get:all'],
                created_permissions['member_all:create:all'],
                created_permissions['member_all:update:all'],
                created_permissions['member_all:delete:all'],
                created_permissions['staff_basic:get:profile_hierarchy'],
                created_permissions['staff_basic:update:own'],
            )
        print(f"{'✓ 創建' if created else '○ 已存在'} {staff_role}")
        print(f"  - 擁有 {staff_role.permissions.count()} 個權限")

        # Admin Role (Staff)
        admin_role, created = RBACRole.objects.get_or_create(
            name='admin_role', defaults={'is_staff_only': True, 'description': '管理員角色'}
        )
        if created:
            admin_role.permissions.add(
                created_permissions['member_all:get:all'],
                created_permissions['member_all:create:all'],
                created_permissions['member_all:update:all'],
                created_permissions['member_all:delete:all'],
                created_permissions['staff_basic:get:all'],
                created_permissions['staff_basic:create:all'],
                created_permissions['staff_basic:update:all'],
                created_permissions['staff_basic:delete:all'],
            )
        print(f"{'✓ 創建' if created else '○ 已存在'} {admin_role}")
        print(f"  - 擁有 {admin_role.permissions.count()} 個權限")

        # 為現有用戶分配角色
        print('\n分配用戶角色...')

        # 為所有 Member 分配對應角色
        tourists = Member.objects.filter(type=Member.TypeOptions.TOURIST)
        for member in tourists:
            member.rbac_roles.add(tourist_role)
        print(f"✓ 為 {tourists.count()} 個 Tourist 分配角色")

        real_members = Member.objects.filter(type=Member.TypeOptions.REAL)
        for member in real_members:
            member.rbac_roles.add(real_member_role)
        print(f"✓ 為 {real_members.count()} 個 Real Member 分配角色")

        # 為所有 Staff 分配對應角色
        staffs = Staff.objects.filter(type=Staff.TypeOptions.STAFF)
        for staff in staffs:
            staff.rbac_roles.add(staff_role)
        print(f"✓ 為 {staffs.count()} 個 Staff 分配角色")

        admins = Staff.objects.filter(type=Staff.TypeOptions.ADMIN)
        for admin in admins:
            admin.rbac_roles.add(admin_role)
        print(f"✓ 為 {admins.count()} 個 Admin 分配角色")

        print(f"\n🎉 RBAC 初始化完成！")
        print(f"總計創建:")
        print(f"  - 3 個 Scope")
        print(f"  - {len(permissions_data)} 個 RBACPermission")
        print(f"  - 4 個 Role")
        print(f"總計分配角色:")
        print(f"  - {tourists.count()} 個 Tourist")
        print(f"  - {real_members.count()} 個 Real Member")
        print(f"  - {staffs.count()} 個 Staff")
        print(f"  - {admins.count()} 個 Admin")
