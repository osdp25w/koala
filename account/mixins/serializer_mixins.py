import logging

logger = logging.getLogger(__name__)


class RBACSerializerMixin:
    """RBAC Serializer 欄位過濾 Mixin"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_field_filtering()

    def apply_field_filtering(self):
        """根據用戶權限過濾欄位"""
        context = self.context
        allowed_fields = context.get('allowed_fields')

        if not allowed_fields:
            return

        # 動態移除沒有權限的欄位
        fields_to_remove = []
        for field_name in self.fields:
            if field_name not in allowed_fields:
                fields_to_remove.append(field_name)

        for field_name in fields_to_remove:
            self.fields.pop(field_name)

        logger.debug(
            f"Serializer field filtering: kept {len(self.fields)} fields, removed {len(fields_to_remove)} fields"
        )

    def to_representation(self, instance):
        """根據權限過濾輸出，支援動態欄位值過濾"""
        data = super().to_representation(instance)

        context = self.context
        field_access_levels = context.get('field_access_levels')
        profile = context.get('profile')

        # 如果有動態權限配置，使用新的邏輯
        if field_access_levels and profile:
            return self._apply_dynamic_field_filtering(
                instance, data, field_access_levels, profile
            )

        # 否則使用舊的靜態過濾邏輯（向後兼容）
        allowed_fields = context.get('allowed_fields')
        if allowed_fields:
            return {
                field: value for field, value in data.items() if field in allowed_fields
            }

        return data

    def _apply_dynamic_field_filtering(
        self, instance, data, field_access_levels, profile
    ):
        """根據權限動態設定欄位值"""
        from utils.constants import RowAccessLevel

        filtered_data = data.copy()  # 保留所有欄位結構

        for field_name in field_access_levels:
            if field_name in filtered_data:
                access_level = field_access_levels[field_name]

                # 如果沒有權限，設為None
                if not self._has_field_access_to_instance(
                    profile, instance, field_name, access_level
                ):
                    filtered_data[field_name] = None
                    logger.debug(
                        f"Set field '{field_name}' to None for user {profile.username}"
                    )

        return filtered_data

    def _has_field_access_to_instance(
        self, profile, instance, field_name, access_level
    ):
        """檢查用戶對特定記錄的特定欄位是否有存取權限"""
        from utils.constants import RowAccessLevel

        if access_level == RowAccessLevel.ALL:
            return True
        elif access_level == RowAccessLevel.OWN:
            return self._is_own_record(profile, instance)
        elif access_level == RowAccessLevel.PROFILE_HIERARCHY:
            return self._is_within_hierarchy(profile, instance)
        else:
            return False

    def _is_own_record(self, profile, instance):
        """檢查記錄是否屬於用戶自己"""
        if hasattr(instance, 'id') and hasattr(profile, 'id'):
            return instance.id == profile.id
        if hasattr(instance, 'user') and hasattr(profile, 'user'):
            return instance.user.id == profile.user.id
        return False

    def _is_within_hierarchy(self, profile, instance):
        """檢查記錄是否在用戶的權限階層內"""
        if self._is_own_record(profile, instance):
            return True

        if hasattr(profile, 'type') and hasattr(instance, 'type'):
            model_class = instance.__class__
            profile_hierarchy = getattr(model_class, 'TYPE_HIERARCHY', {})

            profile_level = profile_hierarchy.get(profile.type, 0)
            instance_level = profile_hierarchy.get(instance.type, 0)

            return instance_level <= profile_level

        return False
