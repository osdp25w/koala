import logging
from typing import Dict, Set

from rest_framework.exceptions import PermissionDenied

from account.models import RBACPermission
from utils.constants import HTTPMethod, RowAccessLevel

logger = logging.getLogger(__name__)


class MockUser:
    """用於權限檢查的模擬 User 物件"""

    def __init__(self, user_id):
        self.id = user_id


class MockInstance:
    """用於權限檢查的模擬實例物件"""

    def __init__(self, data):
        self.id = data.get('id')
        self.type = data.get('type')
        self.user = MockUser(data.get('user_id')) if data.get('user_id') else None


class RBACViewSetMixin:
    RBAC_AUTO_FILTER_FIELDS = True  # 是否自動過濾欄位
    RBAC_AUTO_FILTER_ROWS = True  # 是否自動過濾資料列

    # HTTP method 到 RBACPermission action 的映射
    ACTION_MAPPING = {
        HTTPMethod.GET: RBACPermission.ACTION_GET,
        HTTPMethod.POST: RBACPermission.ACTION_CREATE,
        HTTPMethod.PUT: RBACPermission.ACTION_UPDATE,
        HTTPMethod.PATCH: RBACPermission.ACTION_UPDATE,
        HTTPMethod.DELETE: RBACPermission.ACTION_DELETE,
    }

    def get_rbac_model_class(self):
        """獲取要檢查權限的 Model 類"""
        if hasattr(self, 'queryset') and self.queryset is not None:
            return self.queryset.model
        return super().get_queryset().model

    def get_rbac_action(self) -> str:
        """根據 HTTP method 獲取對應的 RBACPermission action"""
        method = self.request.method
        return self.ACTION_MAPPING.get(method, RBACPermission.ACTION_GET)

    def check_rbac_permission(self) -> bool:
        """檢查 RBAC 權限"""
        if not self.request.user.is_authenticated:
            raise PermissionDenied('用戶未登入')

        if not hasattr(self.request.user, 'profile') or not self.request.user.profile:
            raise PermissionDenied('無權限檔案')

        profile = self.request.user.profile
        model_class = self.get_rbac_model_class()
        action = self.get_rbac_action()

        has_permission = profile.has_model_permission(model_class, action)

        if not has_permission:
            logger.warning(
                f"Permission denied: user={profile.username}, "
                f"model={model_class._meta.label}, action={action}"
            )
            raise PermissionDenied(f"沒有 {model_class._meta.verbose_name} 的 {action} 權限")

        return True

    def get_allowed_fields(self) -> Set[str]:
        """獲取用戶可存取的欄位"""
        if not self.RBAC_AUTO_FILTER_FIELDS:
            return set()

        profile = self.request.user.profile
        model_class = self.get_rbac_model_class()
        action = self.get_rbac_action()

        return profile.get_allowed_fields(model_class, action)

    def initial(self, request, *args, **kwargs):
        """在處理請求前檢查權限"""
        super().initial(request, *args, **kwargs)

        # 如果不支援，DRF 應該已經在 super().initial() 中拋出 MethodNotAllowed
        if hasattr(self, 'action') and self.action:
            # 檢查當前 ViewSet 是否實際支援這個 action
            if hasattr(self, self.action) and callable(getattr(self, self.action)):
                self.check_rbac_permission()

    def get_queryset(self):
        """override get_queryset() to apply RBAC row-level filter"""
        queryset = super().get_queryset()

        if not self.RBAC_AUTO_FILTER_ROWS:
            return queryset

        return self.apply_row_access_filter(queryset)

    def apply_row_access_filter(self, queryset):
        """根據用戶權限過濾 queryset"""
        if not self.request.user.is_authenticated:
            return queryset.none()

        if not hasattr(self.request.user, 'profile') or not self.request.user.profile:
            return queryset.none()

        profile = self.request.user.profile
        model_class = self.get_rbac_model_class()
        action = self.get_rbac_action()

        from account.caches import PermissionCache

        # 獲取所有有權限的欄位及其存取級別（一次性獲取）
        field_access_levels = PermissionCache.get_allowed_fields_with_access(
            profile, model_class, action
        )
        if not field_access_levels:
            return queryset.none()

        # 檢查是否有任何欄位具有不同權限級別
        access_levels = set(field_access_levels.values())
        has_all_access = RowAccessLevel.ALL in access_levels
        has_profile_hierarchy_access = RowAccessLevel.PROFILE_HIERARCHY in access_levels
        has_own_access = RowAccessLevel.OWN in access_levels

        # 根據最高權限級別過濾 queryset
        if has_all_access:
            return queryset  # 可以看所有資料
        elif has_profile_hierarchy_access:
            return self.filter_by_profile_hierarchy(queryset, profile)
        elif has_own_access:
            return self.filter_by_ownership(queryset, profile)

        return queryset.none()

    def filter_by_ownership(self, queryset, profile):
        """過濾只屬於用戶自己的記錄"""
        model_class = queryset.model

        # Member模型：直接比較id
        if hasattr(model_class, '_meta') and model_class._meta.model_name == 'member':
            return queryset.filter(id=profile.id)

        # 其他模型：通過user關聯
        if hasattr(model_class, 'user'):
            return queryset.filter(user=profile.user)

        # 如果找不到合適的過濾條件，返回空集
        logger.warning(f"Cannot determine ownership filter for model {model_class}")
        return queryset.none()

    def filter_by_profile_hierarchy(self, queryset, profile):
        """根據 profile 階層過濾記錄"""
        model_class = queryset.model

        # 獲取 profile 的類型和階層設定
        if not hasattr(profile, 'type') or not hasattr(model_class, 'TYPE_HIERARCHY'):
            logger.warning(
                f"Profile {profile} or model {model_class} missing type hierarchy"
            )
            return self.filter_by_ownership(queryset, profile)

        user_type = profile.type
        type_hierarchy = model_class.TYPE_HIERARCHY
        user_level = type_hierarchy.get(user_type, 0)

        if user_level == 0:
            logger.warning(f"Unknown user type {user_type} for model {model_class}")
            return self.filter_by_ownership(queryset, profile)

        # 過濾：只能存取等級小於等於自己的記錄
        accessible_types = [
            type_name
            for type_name, level in type_hierarchy.items()
            if level <= user_level
        ]

        return queryset.filter(type__in=accessible_types)

    def get_field_access_context(self):
        """獲取欄位存取權限的context資訊"""
        if not self.RBAC_AUTO_FILTER_FIELDS:
            return {}

        profile = (
            self.request.user.profile if hasattr(self.request.user, 'profile') else None
        )
        if not profile:
            return {}

        model_class = self.get_rbac_model_class()
        action = self.get_rbac_action()

        from account.caches import PermissionCache

        # 直接獲取欄位及其權限級別（一次性獲取，更高效）
        return PermissionCache.get_allowed_fields_with_access(
            profile, model_class, action
        )

    def get_serializer_context(self):
        """向 serializer 傳遞權限相關的 context"""
        context = super().get_serializer_context()
        if self.RBAC_AUTO_FILTER_FIELDS:
            context['allowed_fields'] = self.get_allowed_fields()
            context['field_access_levels'] = self.get_field_access_context()
            context['profile'] = getattr(self.request.user, 'profile', None)
            context['model_class'] = self.get_rbac_model_class()
            context['action'] = self.get_rbac_action()
        return context

    def finalize_response(self, request, response, *args, **kwargs):
        """在最終輸出前應用權限過濾"""
        response = super().finalize_response(request, response, *args, **kwargs)

        if (
            self.RBAC_AUTO_FILTER_FIELDS
            and hasattr(response, 'data')
            and response.status_code == 200
        ):
            response.data = self._apply_rbac_to_response_data(response.data)

        return response

    def _apply_rbac_to_response_data(self, data):
        """對最終響應數據應用權限過濾"""
        field_access_levels = self.get_field_access_context()
        profile = getattr(self.request.user, 'profile', None)

        if not field_access_levels or not profile:
            return data

        return self._filter_data_recursively(data, field_access_levels, profile)

    def _filter_data_recursively(self, data, field_access_levels, profile):
        """遞迴處理數據結構，對模型對象應用權限過濾"""
        if isinstance(data, dict):
            return self._filter_dict_data(data, field_access_levels, profile)
        elif isinstance(data, list):
            return [
                self._filter_data_recursively(item, field_access_levels, profile)
                for item in data
            ]
        else:
            return data

    def _filter_dict_data(self, data, field_access_levels, profile):
        """過濾字典數據"""
        if not isinstance(data, dict):
            return data

        filtered_data = data.copy()

        # 檢查是否是模型對象的數據（包含 id 等標識）
        if self._is_model_object_data(data):
            filtered_data = self._apply_field_filtering(
                data, field_access_levels, profile
            )

        # 遞迴處理嵌套結構
        for key, value in filtered_data.items():
            filtered_data[key] = self._filter_data_recursively(
                value, field_access_levels, profile
            )

        return filtered_data

    def _is_model_object_data(self, data):
        """判斷數據是否為模型對象數據"""
        if not isinstance(data, dict):
            return False
        # 簡單判斷：包含 id 欄位的字典可能是模型對象
        return 'id' in data

    def _apply_field_filtering(self, data, field_access_levels, profile):
        """根據權限動態設定欄位值"""
        from utils.constants import RowAccessLevel

        filtered_data = data.copy()

        # 創建一個模擬實例對象以便進行權限檢查
        mock_instance = MockInstance(data)

        for field_name in field_access_levels:
            if field_name in filtered_data:
                access_level = field_access_levels[field_name]

                # 如果沒有權限，設為 None
                if not self._has_field_access_to_instance(
                    profile, mock_instance, field_name, access_level
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
        if hasattr(instance, 'user') and hasattr(profile, 'user') and instance.user:
            return instance.user.id == profile.user.id
        return False

    def _is_within_hierarchy(self, profile, instance):
        """檢查記錄是否在用戶的權限階層內"""
        if self._is_own_record(profile, instance):
            return True

        if hasattr(profile, 'type') and hasattr(instance, 'type'):
            model_class = self.get_rbac_model_class()
            profile_hierarchy = getattr(model_class, 'TYPE_HIERARCHY', {})

            profile_level = profile_hierarchy.get(profile.type, 0)
            instance_level = profile_hierarchy.get(instance.type, 0)

            return instance_level <= profile_level

        return False
