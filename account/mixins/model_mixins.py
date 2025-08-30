from typing import Dict, Set

from django.db import models


class RBACPermissionModelMixin(models.Model):
    """Model 權限檢查 Mixin - 為 User Profile 模型提供權限方法"""

    class Meta:
        abstract = True

    def get_allowed_fields(self, model_class, action: str) -> Set[str]:
        """獲取用戶可存取的欄位列表（從緩存，不打 DB）"""
        from account.caches import PermissionCache

        return PermissionCache.get_allowed_fields(self, model_class, action)

    def get_allowed_fields_with_access(
        self, model_class, action: str
    ) -> Dict[str, int]:
        """獲取用戶可存取的欄位及其權限級別（從緩存，不打 DB）"""
        from account.caches import PermissionCache

        return PermissionCache.get_allowed_fields_with_access(self, model_class, action)

    def get_field_access_level(self, model_class, action: str, field_name: str) -> int:
        """獲取特定欄位的存取權限級別（從緩存，不打 DB）"""
        from account.caches import PermissionCache

        return PermissionCache.get_field_access_level(
            self, model_class, action, field_name
        )

    def has_model_permission(self, model_class, action: str) -> bool:
        """檢查用戶是否有特定 model 的權限（從緩存，不打 DB）"""
        from account.caches import PermissionCache

        return PermissionCache.has_model_permission(self, model_class, action)

    def has_field_permission(
        self, model_class, action: str, field_name: str, required_level: int = 1
    ) -> bool:
        """檢查用戶是否有特定欄位的權限（從緩存，不打 DB）"""
        access_level = self.get_field_access_level(model_class, action, field_name)
        return access_level >= required_level
