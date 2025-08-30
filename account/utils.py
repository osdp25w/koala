import logging
from typing import Dict

from django.apps import apps
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ModelFieldBitMap:
    """管理 Model 欄位到 bit position 的映射"""

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
            fields = cls._get_api_field_names(model_class)
            bit_map = {field: idx for idx, field in enumerate(fields)}
            cache.set(cache_key, bit_map, timeout=86400)  # 24小時
            logger.info(f"Generated field bit map for {model_class._meta.label}")

        return bit_map

    @classmethod
    def _get_api_field_names(cls, model_class) -> list:
        """獲取對外API應該使用的欄位名稱，正確處理加密欄位"""
        api_fields = []

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
                    api_fields.append(property_name)  # 使用property名稱
                # 否則跳過這個內部欄位
                continue
            else:
                # 一般欄位直接使用
                api_fields.append(field_name)

        return sorted(api_fields)

    @classmethod
    def update_field_map(cls, model_class):
        """更新 model 的欄位映射（在 model 變更時調用）"""
        cache_key = cls._compose_cache_key(model_class._meta.model_name)
        fields = cls._get_api_field_names(model_class)
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
