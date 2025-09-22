import logging
from collections import defaultdict
from typing import Dict, Set

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from account.models import RBACPermission, UserProfile
from account.utils import RBACPermissionBitMapService
from utils.constants import RowAccessLevel

logger = logging.getLogger(__name__)


class TokenBlacklistCache:
    CACHE_TIMEOUT = 60 * 60 * 24
    CACHE_KEY_PATTERN = 'token_blacklist:{token_jti}'

    @classmethod
    def _compose_cache_key(cls, token_jti: str) -> str:
        return cls.CACHE_KEY_PATTERN.format(token_jti=token_jti)

    @classmethod
    def add_token_to_blacklist(cls, token_jti: str) -> None:
        """將token JTI加入黑名單"""
        cache_key = cls._compose_cache_key(token_jti)
        cache.set(cache_key, True, cls.CACHE_TIMEOUT)
        logger.info(f"Added token {token_jti} to blacklist")

    @classmethod
    def is_token_blacklisted(cls, token_jti: str) -> bool:
        """檢查token是否在黑名單中"""
        cache_key = cls._compose_cache_key(token_jti)
        return cache.get(cache_key, False)

    @classmethod
    def remove_token_from_blacklist(cls, token_jti: str) -> None:
        """從黑名單中移除token"""
        cache_key = cls._compose_cache_key(token_jti)
        cache.delete(cache_key)
        logger.info(f"Removed token {token_jti} from blacklist")


class PermissionCache:
    CACHE_TIMEOUT = 60 * 60 * 24  # 1 day
    CACHE_KEY_PATTERN = 'perms:{profile_type}:{profile_id}:{model_name}'

    @classmethod
    def _compose_cache_key(cls, profile: UserProfile, model_name: str) -> str:
        """獲取快取 key"""
        return cls.CACHE_KEY_PATTERN.format(
            profile_type=profile._meta.model_name,
            profile_id=profile.id,
            model_name=model_name,
        )

    @classmethod
    def get_model_permission_bitmasks(
        cls, profile: UserProfile, model_class
    ) -> Dict[str, int]:
        """獲取用戶對特定模型的權限 Bitmask
        返回格式: {'get': bitmask_int, 'create': bitmask_int, ...}
        """
        model_name = model_class._meta.model_name
        cache_key = cls._compose_cache_key(profile, model_name)
        model_perms = cache.get(cache_key)

        if model_perms is None:
            model_perms = cls._build_model_permission_bitmasks(profile, model_class)
            cache.set(cache_key, model_perms, cls.CACHE_TIMEOUT)
            logger.info(
                f"Cached {model_name} permissions for {profile._meta.model_name} {profile.username}"
            )

        return model_perms

    @classmethod
    def _build_model_permission_bitmasks(
        cls, profile: UserProfile, model_class
    ) -> Dict[str, int]:
        """構建用戶對特定模型的權限 Bitmask（四進制壓縮）"""
        content_type = ContentType.objects.get_for_model(model_class)

        # 查詢該用戶對此模型的所有權限
        permissions = (
            RBACPermission.objects.filter(
                rbac_roles__in=profile.rbac_roles.all(),
                scope__related_model=content_type,
                scope__is_active=True,
            )
            .select_related('scope')
            .distinct()
        )

        # 按 action 分組收集欄位和對應的row_access
        action_field_access = defaultdict(lambda: defaultdict(int))
        for perm in permissions:
            # 計算有效欄位
            effective_fields = perm.scope.get_effective_fields()

            # 將row_access轉換為數值
            access_level = cls._get_access_level(perm.row_access)

            for field in effective_fields:
                # 取最高權限（如果同個欄位有多個Permission）
                action_field_access[perm.action][field] = max(
                    action_field_access[perm.action][field], access_level
                )

        # 將欄位權限壓縮為四進制bitmask
        compressed_perms = {}
        for action, field_access in action_field_access.items():
            bitmask = RBACPermissionBitMapService.encode_field_permissions_to_bitmask(
                model_class, field_access
            )
            compressed_perms[action] = bitmask

        return compressed_perms

    @classmethod
    def _get_access_level(cls, row_access: str) -> int:
        """將row_access字串轉換為數值"""
        return RowAccessLevel.from_string(row_access)

    @classmethod
    def get_allowed_fields(
        cls, profile: UserProfile, model_class, action: str
    ) -> Set[str]:
        """直接從緩存獲取允許的欄位，不打 DB"""
        model_perms = cls.get_model_permission_bitmasks(profile, model_class)
        bitmask = model_perms.get(action, 0)

        return RBACPermissionBitMapService.get_allowed_fields_from_bitmask(
            model_class, bitmask
        )

    @classmethod
    def get_allowed_fields_with_access(
        cls, profile: UserProfile, model_class, action: str
    ) -> Dict[str, int]:
        """獲取允許的欄位及其存取權限級別
        Returns: {'field_name': access_level, ...}
        """
        model_perms = cls.get_model_permission_bitmasks(profile, model_class)
        bitmask = model_perms.get(action, 0)

        return RBACPermissionBitMapService.get_allowed_fields_with_access_from_bitmask(
            model_class, bitmask
        )

    @classmethod
    def get_field_access_level(
        cls, profile: UserProfile, model_class, action: str, field_name: str
    ) -> int:
        """獲取特定欄位的存取權限級別 (0=none, 1=own, 2=profile_hierarchy, 3=all)"""
        model_perms = cls.get_model_permission_bitmasks(profile, model_class)
        bitmask = model_perms.get(action, 0)

        if bitmask == 0:
            return 0

        bit_map = RBACPermissionBitMapService.get_field_bit_map(model_class)
        if field_name not in bit_map:
            return 0

        bit_pos = bit_map[field_name]
        return RBACPermissionBitMapService.get_field_access_level_from_bitmask(
            bitmask, bit_pos
        )

    @classmethod
    def has_model_permission(
        cls, profile: UserProfile, model_class, action: str
    ) -> bool:
        """直接從緩存檢查權限，不打 DB"""
        model_perms = cls.get_model_permission_bitmasks(profile, model_class)
        return model_perms.get(action, 0) > 0

    @classmethod
    def clear_profile_cache(cls, profile: UserProfile) -> None:
        """清除用戶的所有權限緩存"""
        profile_type = profile._meta.model_name
        pattern = f"perms:{profile_type}:{profile.id}:*"

        try:
            cache.delete_pattern(pattern)
            logger.info(
                f"Cleared all permission cache for {profile_type} {profile.username}"
            )
        except AttributeError:
            logger.warning(
                f"Cache backend doesn't support pattern deletion for {pattern}"
            )

    @classmethod
    def clear_model_cache(cls, model_class) -> None:
        """清除特定模型的所有權限緩存"""
        model_name = model_class._meta.model_name
        pattern = f"perms:*:*:{model_name}"

        try:
            cache.delete_pattern(pattern)
            logger.info(f"Cleared all permission cache for model {model_name}")
        except AttributeError:
            logger.warning(
                f"Cache backend doesn't support pattern deletion for {pattern}"
            )

    @classmethod
    def clear_profile_model_cache(cls, profile: UserProfile, model_class) -> None:
        """清除特定用戶對特定模型的權限緩存"""
        model_name = model_class._meta.model_name
        cache_key = cls._compose_cache_key(profile, model_name)

        cache.delete(cache_key)
        logger.info(
            f"Cleared {model_name} permission cache for {profile._meta.model_name} {profile.username}"
        )

    @classmethod
    def clear_all_cache(cls) -> None:
        """清除所有權限緩存"""
        try:
            cache.delete_pattern('perms:*')
            logger.info('Cleared all permission cache')
        except AttributeError:
            logger.warning(
                "Cache backend doesn't support pattern deletion. Consider manual cleanup."
            )
