import logging
from typing import Dict

from django.apps import apps
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RBACPermissionBitMapService:
    """RBAC 權限 Bitmask 服務 - 管理模型欄位權限的位元映射與編碼解碼"""

    CACHE_KEY_PATTERN = 'field_bit_map:{model_name}'

    @classmethod
    def _compose_cache_key(cls, model_name: str) -> str:
        return cls.CACHE_KEY_PATTERN.format(model_name=model_name)

    @classmethod
    def get_field_bit_map(cls, model_class) -> Dict[str, int]:
        """獲取 model 的欄位 bit mapping"""
        cache_key = cls._compose_cache_key(model_class._meta.model_name)
        bit_map = cache.get(cache_key)

        if not bit_map:
            fields = cls._resolve_model_fields(model_class)
            bit_map = {field: idx for idx, field in enumerate(fields)}
            cache.set(cache_key, bit_map)
            logger.info(f"Generated field bit map for {model_class._meta.label}")

        return bit_map

    @classmethod
    def _resolve_model_fields(cls, model_class) -> list:
        """解析模型欄位名稱，正確處理加密欄位"""
        resolved_fields = []

        for field in model_class._meta.fields:
            field_name = field.name

            # 跳過Django內建的特殊欄位
            if field_name.startswith('_') and field_name.endswith('_'):
                continue

            # 處理加密欄位：如果是以_開頭的欄位且model有對應的property
            if field_name.startswith('_'):
                property_name = field_name[1:]  # 移除開頭的_

                # 檢查是否有對應的property（加密欄位）
                if hasattr(model_class, property_name) and isinstance(
                    getattr(model_class, property_name), property
                ):
                    resolved_fields.append(property_name)  # 使用property名稱
                # 否則跳過這個內部欄位
                continue
            else:
                # 一般欄位直接使用
                resolved_fields.append(field_name)

        return sorted(resolved_fields)

    @classmethod
    def update_field_map(cls, model_class):
        """更新 model 的欄位映射（在 model 變更時調用）"""
        cache_key = cls._compose_cache_key(model_class._meta.model_name)
        fields = cls._resolve_model_fields(model_class)
        new_bit_map = {field: idx for idx, field in enumerate(fields)}

        old_bit_map = cache.get(cache_key)
        if old_bit_map != new_bit_map:
            cache.set(cache_key, new_bit_map, timeout=86400)
            # 清除相關的權限快取
            cls._clear_model_permission_cache(model_class)
            logger.info(f"Updated field bit map for {model_class._meta.model_name}")

    @classmethod
    def _clear_model_permission_cache(cls, model_class):
        """清除特定 model 的權限快取"""
        # 這裡需要根據你的快取 pattern 來實作
        try:
            model_name = model_class._meta.model_name
            cache.delete_pattern(f"perms:*:*:{model_name}")
        except AttributeError:
            logger.warning("Cache backend doesn't support pattern deletion")

    # Bitmask 編碼/解碼相關方法
    @classmethod
    def encode_field_permissions_to_bitmask(cls, model_class, field_access_dict) -> int:
        """將欄位權限字典編碼為 bitmask
        Args:
            model_class: 模型類別
            field_access_dict: {'field_name': access_level, ...}
        Returns:
            壓縮後的 bitmask 整數
        """
        bit_map = cls.get_field_bit_map(model_class)
        bitmask = 0

        for field, access_level in field_access_dict.items():
            if field in bit_map:
                bit_pos = bit_map[field]
                # 每個欄位使用2個bits儲存權限級別
                bitmask |= access_level << (bit_pos * 2)

        return bitmask

    @classmethod
    def get_allowed_fields_from_bitmask(cls, model_class, bitmask: int):
        """從 bitmask 提取允許的欄位集合"""
        from utils.constants import RowAccessLevel

        if bitmask == 0:
            return set()

        bit_map = cls.get_field_bit_map(model_class)
        fields = set()

        for field, bit_pos in bit_map.items():
            field_access = cls.get_field_access_level_from_bitmask(bitmask, bit_pos)
            if field_access > RowAccessLevel.NONE:
                fields.add(field)

        return fields

    @classmethod
    def get_allowed_fields_with_access_from_bitmask(cls, model_class, bitmask: int):
        """從 bitmask 提取允許的欄位及其存取權限級別"""
        from utils.constants import RowAccessLevel

        if bitmask == 0:
            return {}

        bit_map = cls.get_field_bit_map(model_class)
        field_access_dict = {}

        for field, bit_pos in bit_map.items():
            field_access = cls.get_field_access_level_from_bitmask(bitmask, bit_pos)
            if field_access > RowAccessLevel.NONE:
                field_access_dict[field] = field_access

        return field_access_dict

    @classmethod
    def get_field_access_level_from_bitmask(cls, bitmask: int, bit_pos: int) -> int:
        """從 bitmask 中提取特定欄位的權限級別"""
        # 每個欄位使用2個bits，所以實際位置是 bit_pos * 2
        shift = bit_pos * 2
        # 使用mask 0b11 (3) 提取2個bits
        return (bitmask >> shift) & 0b11
