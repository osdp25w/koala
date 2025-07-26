import logging
from typing import List

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Prefetch, QuerySet

from account.models import Member, Permission, Role, Staff

logger = logging.getLogger(__name__)


class PermissionHelper:
    """權限處理助手類"""

    # 快取設定
    CACHE_TIMEOUT = 60 * 60 * 24  # 24小時
    CACHE_PREFIX_USER_PERMISSIONS = 'user_perms'
    CACHE_PREFIX_ROLE_PERMISSIONS = 'role_perms'

    @classmethod
    def get_all_permissions(cls, user: User) -> QuerySet[Permission]:
        # 檢查快取
        cache_key = cls._get_user_cache_key(user)
        cached_permissions = cache.get(cache_key)

        if cached_permissions is not None:
            logger.debug(f"從快取獲取權限: {user}")
            return cached_permissions

        # 計算權限
        permissions = cls._calculate_all_permissions(user)

        # 存入快取
        cache.set(cache_key, permissions, cls.CACHE_TIMEOUT)
        logger.debug(f"權限計算完成並快取: {user}")

        return permissions

    @classmethod
    def _calculate_all_permissions(cls, user: User) -> QuerySet[Permission]:
        """計算用戶所有權限"""
        from account.models import Permission

        # 收集所有權限 ID
        permission_ids = set()

        # 1. 獲取直接權限
        direct_permission_ids = set(
            user.direct_permissions.values_list('id', flat=True)
        )
        permission_ids.update(direct_permission_ids)
        logger.debug(f"直接權限數量: {len(direct_permission_ids)}")

        # 2. 獲取角色權限（包含繼承）
        role_permission_ids = cls._get_role_permissions(user)
        permission_ids.update(role_permission_ids)
        logger.debug(f"角色權限數量: {len(role_permission_ids)}")

        # 3. 返回優化的查詢集
        return (
            Permission.objects.filter(id__in=permission_ids)
            .select_related('resource')
            .order_by('resource__code', 'action')
        )

    @classmethod
    def _get_role_permissions(cls, user_instance):
        """獲取角色相關的所有權限 ID"""
        # 獲取所有角色（包含繼承）
        all_roles = cls._get_all_roles_with_inheritance(user)

        if not all_roles:
            return set()

        # 批量獲取權限集合的權限
        permission_ids = set()

        # 使用 prefetch_related 優化查詢
        roles_with_permissions = user.roles.filter(
            id__in=[role.id for role in all_roles]
        ).prefetch_related(
            Prefetch(
                'permission_sets__permissions',
                queryset=user.__class__._meta.get_field(
                    'direct_permissions'
                ).related_model.objects.select_related('resource'),
            )
        )

        for role in roles_with_permissions:
            for permission_set in role.permission_sets.all():
                perm_ids = permission_set.permissions.values_list('id', flat=True)
                permission_ids.update(perm_ids)

        return permission_ids

    @classmethod
    def _get_all_roles_with_inheritance(cls, user: User) -> List[Role]:
        """獲取用戶所有角色（包含繼承的角色）"""
        from account.models import Role

        # 獲取用戶直接角色
        direct_roles = list(user.roles.all())
        all_roles = set(direct_roles)

        # 遞歸獲取父角色
        for role in direct_roles:
            parent_roles = cls._get_parent_roles_recursive(role)
            all_roles.update(parent_roles)

        return list(all_roles)

    @classmethod
    def _get_parent_roles_recursive(cls, role, visited=None):
        """遞歸獲取父角色，避免循環引用"""
        if visited is None:
            visited = set()

        # 防止循環引用
        if role.id in visited:
            logger.warning(f"檢測到角色繼承循環: {role}")
            return []

        visited.add(role.id)
        parent_roles = []

        if role.parent:
            parent_roles.append(role.parent)
            # 遞歸獲取祖父角色
            grandparent_roles = cls._get_parent_roles_recursive(
                role.parent, visited.copy()
            )
            parent_roles.extend(grandparent_roles)

        return parent_roles

    @classmethod
    def _get_user_cache_key(cls, user: User) -> str:
        """生成用戶權限快取鍵"""
        model_name = user.__class__.__name__.lower()
        return f"{cls.CACHE_PREFIX_USER_PERMISSIONS}:{model_name}:{user.id}"

    @classmethod
    def clear_user_permissions_cache(cls, user: User):
        """清除用戶權限快取"""
        cache_key = cls._get_user_cache_key(user)
        cache.delete(cache_key)
        logger.info(f"清除權限快取: {user}")

    @classmethod
    def clear_all_permissions_cache(cls):
        """清除所有權限快取（在權限/角色變更時使用）"""
        # 這裡可以實現更精細的快取清理邏輯
        cache.clear()
        logger.info('清除所有權限快取')

    @classmethod
    def get_permissions_by_resource(
        cls, user: User, resource_code: str
    ) -> QuerySet[Permission]:
        """獲取用戶對特定資源的所有權限"""
        all_permissions = cls.get_all_permissions(user)
        return all_permissions.filter(resource__code=resource_code)

    @classmethod
    def get_permissions_by_action(cls, user: User, action: str) -> QuerySet[Permission]:
        """獲取用戶特定動作的所有權限"""
        all_permissions = cls.get_all_permissions(user)
        return all_permissions.filter(action=action)

    @classmethod
    def get_user_resources(cls, user: User) -> Set[str]:
        """獲取用戶有權限的所有資源"""
        all_permissions = cls.get_all_permissions(user)
        return set(all_permissions.values_list('resource__code', flat=True))

    @classmethod
    def get_permission_summary(cls, user_instance):
        """獲取權限總覽"""
        all_permissions = cls.get_all_permissions(user_instance)

        summary = {
            'total_permissions': all_permissions.count(),
            'resources': {},
            'actions': {},
        }

        for perm in all_permissions:
            resource_code = perm.resource.code
            action = perm.action

            # 按資源統計
            if resource_code not in summary['resources']:
                summary['resources'][resource_code] = []
            summary['resources'][resource_code].append(action)

            # 按動作統計
            if action not in summary['actions']:
                summary['actions'][action] = []
            summary['actions'][action].append(resource_code)

        return summary


class PermissionCacheManager:
    """權限快取管理器"""

    @staticmethod
    def invalidate_user_cache(user_instance):
        """當用戶權限變更時調用"""
        PermissionHelper.clear_user_permissions_cache(user_instance)

    @staticmethod
    def invalidate_role_cache(role_instance):
        """當角色權限變更時調用"""
        # 清除所有使用該角色的用戶快取
        from account.models import Member, Staff

        # 清除 Member 快取
        for member in Member.objects.filter(roles=role_instance):
            PermissionHelper.clear_user_permissions_cache(member)

        # 清除 Staff 快取
        for staff in Staff.objects.filter(roles=role_instance):
            PermissionHelper.clear_user_permissions_cache(staff)

    @staticmethod
    def invalidate_permission_set_cache(permission_set_instance):
        """當權限集合變更時調用"""
        # 清除所有使用該權限集合的角色相關用戶快取
        from account.models import Member, Staff

        roles = permission_set_instance.role_set.all()
        for role in roles:
            PermissionCacheManager.invalidate_role_cache(role)
