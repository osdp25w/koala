import logging
from enum import member
from typing import List, Optional, Set

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PermissionSetCache:
    """權限集合快取"""

    CACHE_TIMEOUT = 60 * 60 * 24  # 24小時
    CACHE_KEY = 'permission_set:{permission_set_id}'

    @classmethod
    def _compose_cache_key(cls, permission_set_id: int) -> str:
        return cls.CACHE_KEY.format(permission_set_id=permission_set_id)

    @classmethod
    def get_permission_ids(
        cls, permission_set_id: int, force_refresh: bool = False
    ) -> Set[int]:
        """獲取權限集合的權限 ID"""
        if not force_refresh:
            cache_key = cls._compose_cache_key(permission_set_id)
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                return set(cached_ids)

        # 從資料庫獲取
        permission_ids = cls._fetch_permission_ids_from_db(permission_set_id)
        cache_key = cls._compose_cache_key(permission_set_id)
        cache.set(cache_key, list(permission_ids), cls.CACHE_TIMEOUT)

        return permission_ids

    @classmethod
    def clear(cls, permission_set_id: int):
        """清除權限集合快取"""
        cache_key = cls._compose_cache_key(permission_set_id)
        cache.delete(cache_key)

    @classmethod
    def _fetch_permission_ids_from_db(cls, permission_set_id: int) -> Set[int]:
        """從資料庫獲取權限集合的權限 ID"""
        try:
            from account.models import PermissionSet

            permission_set = PermissionSet.objects.get(id=permission_set_id)
            return set(permission_set.permissions.values_list('id', flat=True))
        except PermissionSet.DoesNotExist:
            return set()


class UserRoleCache:
    CACHE_TIMEOUT = 60 * 60 * 24  # 24小時
    CACHE_KEY = 'user:{user_id}'


class RolePermissionCache:
    CACHE_TIMEOUT = 60 * 60 * 24  # 24小時
    CACHE_KEY = 'role:{role_id}'

    @classmethod
    def _compose_cache_key(cls, role_id: int) -> str:
        return cls.CACHE_KEY.format(role_id=role_id)

    @classmethod
    def get_role_permission_ids(
        cls, role_id: int, force_refresh: bool = False
    ) -> Set[int]:
        if not force_refresh:
            cache_key = cls._compose_cache_key(role_id)
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                return set(cached_ids)

        permission_ids = cls._fetch_role_permissions(role_id)
        cache_key = cls._compose_cache_key(role_id)
        cache.set(cache_key, list(permission_ids), cls.CACHE_TIMEOUT)

        return permission_ids

    @classmethod
    def get_member_roles(cls, force_refresh: bool = False) -> List[int]:
        """獲取 Member 可用角色 ID (is_staff_only=False)"""
        if not force_refresh:
            cached_ids = cache.get(cls.MEMBER_ROLES_KEY)
            if cached_ids is not None:
                return cached_ids

        # 從資料庫獲取
        from account.models import Role

        role_ids = list(
            Role.objects.filter(is_staff_only=False).values_list('id', flat=True)
        )
        cache.set(cls.MEMBER_ROLES_KEY, role_ids, cls.CACHE_TIMEOUT)

        return role_ids

    @classmethod
    def get_all_roles(cls, force_refresh: bool = False) -> List[int]:
        """獲取所有角色 ID (Staff 可用)"""
        if not force_refresh:
            cached_ids = cache.get(cls.ALL_ROLES_KEY)
            if cached_ids is not None:
                return cached_ids

        # 從資料庫獲取
        from account.models import Role

        role_ids = list(Role.objects.values_list('id', flat=True))
        cache.set(cls.ALL_ROLES_KEY, role_ids, cls.CACHE_TIMEOUT)

        return role_ids

    @classmethod
    def clear(cls, role_id: int):
        """清除角色快取"""
        cache_key = cls._compose_cache_key(role_id)
        cache.delete(cache_key)

    @classmethod
    def clear_role_lists(cls):
        """清除角色列表快取"""
        cache.delete_many([cls.MEMBER_ROLES_KEY, cls.ALL_ROLES_KEY])

    @classmethod
    def _fetch_role_permissions(cls, role_id: int) -> Set[int]:
        """計算角色的所有權限"""
        try:
            from account.models import Role

            role = Role.objects.get(id=role_id)

            all_permissions = set()
            permission_set_ids = role.permission_sets.values_list('id', flat=True)

            for permission_set_id in permission_set_ids:
                permission_ids = PermissionSetCache.get_permission_ids(
                    permission_set_id
                )
                all_permissions.update(permission_ids)

            return all_permissions
        except Role.DoesNotExist:
            return set()


class UserPermissionCache:
    CACHE_TIMEOUT = 60 * 60 * 24  # 24小時
    CACHE_KEY = 'user_permissions:{user_id}'

    @classmethod
    def _compose_cache_key(cls, user_id: int) -> str:
        return cls.CACHE_KEY.format(user_id=user_id)

    @classmethod
    def set_permission_ids(cls, user_id: int, permission_ids: Set[int]):
        cache_key = cls._compose_cache_key(user_id=user_id)
        cache.set(cache_key, list(permission_ids), cls.CACHE_TIMEOUT)

    @classmethod
    def get_user_permission_ids(
        cls, user_id: int, force_refresh: bool = False
    ) -> Set[int]:
        cache_key = cls._compose_cache_key(user_id=user_id)

        if not force_refresh:
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                return set(cached_ids)

        permission_ids = cls._fetch_user_permissions(user_id)
        cache.set(cache_key, list(permission_ids), cls.CACHE_TIMEOUT)

        return permission_ids

    @classmethod
    def clear_user_permissions(cls, user_id: int):
        cache_key = cls._compose_cache_key(user_id=user_id)
        cache.delete(cache_key)

    @classmethod
    def _fetch_user_permissions(cls, user_id: int) -> Set[int]:
        user = User.objects.filter(id=user_id).first()
        if user is None:
            logger.warning(f"User {user_id} not found")
            return set()

        user_profile = None
        if hasattr(user, 'staff'):
            user_profile = user.staff
        elif hasattr(user, 'member'):
            user_profile = user.member
        else:
            logger.warning(f"User {user_id} has no staff or member profile")
            return set()

        # direct permissions
        all_permissions = set()
        if user_profile:
            direct_permission_ids = set(
                user_profile.direct_permissions.values_list('id', flat=True)
            )
            all_permissions.update(direct_permission_ids)

        # role permissions
        role_ids = user_profile.roles.values_list('id', flat=True)
        for role_id in role_ids:
            role_permission_ids = RoleCache.get_role_permission_ids(role_id)
            all_permissions.update(role_permission_ids)

        return all_permissions
