import logging
from typing import Dict, Set

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from account.models import RBACPermission, UserProfile
from account.utils import ModelFieldBitMap
from utils.constants import RowAccessLevel

logger = logging.getLogger(__name__)


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
    def get_model_permissions(cls, profile: UserProfile, model_class) -> Dict[str, int]:
        """獲取用戶對特定模型的權限（Bitmask 壓縮）
        返回格式: {'get': bitmask_int, 'create': bitmask_int, ...}
        """
        model_name = model_class._meta.model_name
        cache_key = cls._compose_cache_key(profile, model_name)
        model_perms = cache.get(cache_key)

        if model_perms is None:
            model_perms = cls._build_model_permissions(profile, model_class)
            cache.set(cache_key, model_perms, cls.CACHE_TIMEOUT)
            logger.info(
                f"Cached {model_name} permissions for {profile._meta.model_name} {profile.username}"
            )

        return model_perms

    @classmethod
    def _build_model_permissions(
        cls, profile: UserProfile, model_class
    ) -> Dict[str, int]:
        """構建用戶對特定模型的權限（四進制 Bitmask 版）"""
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
        action_field_access = {}
        for perm in permissions:
            if perm.action not in action_field_access:
                action_field_access[perm.action] = {}

            # 計算有效欄位
            effective_fields = perm.scope.get_effective_fields()

            # 將row_access轉換為數值
            access_level = cls._get_access_level(perm.row_access)

            for field in effective_fields:
                # 取最高權限（如果同個欄位有多個Permission）
                current_level = action_field_access[perm.action].get(field, 0)
                action_field_access[perm.action][field] = max(
                    current_level, access_level
                )

        # 將欄位權限壓縮為四進制bitmask
        bit_map = ModelFieldBitMap.get_field_bit_map(model_class)
        compressed_perms = {}

        for action, field_access in action_field_access.items():
            bitmask = 0
            for field, access_level in field_access.items():
                if field in bit_map:
                    bit_pos = bit_map[field]
                    # 每個欄位使用2個bits儲存權限級別
                    bitmask |= access_level << (bit_pos * 2)
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
        """直接從緩存獲取允許的欄位，不打 DB（四進制 Bitmask 解壓縮版）"""
        model_perms = cls.get_model_permissions(profile, model_class)
        bitmask = model_perms.get(action, 0)

        if bitmask == 0:
            return set()

        # 將四進制 bitmask 解壓縮為欄位集合
        bit_map = ModelFieldBitMap.get_field_bit_map(model_class)
        fields = set()
        for field, bit_pos in bit_map.items():
            # 提取該欄位的2個bits
            field_access = cls._get_field_access_level(bitmask, bit_pos)
            if field_access > RowAccessLevel.NONE:  # 有權限
                fields.add(field)

        return fields

    @classmethod
    def get_allowed_fields_with_access(
        cls, profile: UserProfile, model_class, action: str
    ) -> Dict[str, int]:
        """獲取允許的欄位及其存取權限級別
        Returns: {'field_name': access_level, ...}
        """
        model_perms = cls.get_model_permissions(profile, model_class)
        bitmask = model_perms.get(action, 0)

        if bitmask == 0:
            return {}

        # 將四進制 bitmask 解壓縮為欄位及權限級別字典
        bit_map = ModelFieldBitMap.get_field_bit_map(model_class)
        field_access_dict = {}

        for field, bit_pos in bit_map.items():
            # 提取該欄位的2個bits
            field_access = cls._get_field_access_level(bitmask, bit_pos)
            if field_access > RowAccessLevel.NONE:  # 有權限
                field_access_dict[field] = field_access

        return field_access_dict

    @classmethod
    def get_field_access_level(
        cls, profile: UserProfile, model_class, action: str, field_name: str
    ) -> int:
        """獲取特定欄位的存取權限級別 (0=none, 1=own, 2=profile_hierarchy, 3=all)"""
        model_perms = cls.get_model_permissions(profile, model_class)
        bitmask = model_perms.get(action, 0)

        if bitmask == 0:
            return 0

        bit_map = ModelFieldBitMap.get_field_bit_map(model_class)
        if field_name not in bit_map:
            return 0

        bit_pos = bit_map[field_name]
        return cls._get_field_access_level(bitmask, bit_pos)

    @classmethod
    def _get_field_access_level(cls, bitmask: int, bit_pos: int) -> int:
        """從bitmask中提取特定欄位的權限級別"""
        # 每個欄位使用2個bits，所以實際位置是 bit_pos * 2
        shift = bit_pos * 2
        # 使用mask 0b11 (3) 提取2個bits
        return (bitmask >> shift) & 0b11

    @classmethod
    def has_model_permission(
        cls, profile: UserProfile, model_class, action: str
    ) -> bool:
        """直接從緩存檢查權限，不打 DB"""
        model_perms = cls.get_model_permissions(profile, model_class)
        return model_perms.get(action, 0) > 0

    @classmethod
    def clear_user_cache(cls, profile: UserProfile) -> None:
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
    def clear_user_model_cache(cls, profile: UserProfile, model_class) -> None:
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
