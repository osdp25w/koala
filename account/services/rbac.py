from typing import TYPE_CHECKING, List, Set

from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from account.models import RBACModelPermissionScope, RBACPermission, RBACRole


class RBACModelPermissionScopeModelService:
    @staticmethod
    def get_ancestors(scope) -> list['RBACModelPermissionScope']:
        ancestors = []
        current = scope.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    @staticmethod
    def get_inheritance_chain(scope) -> List['RBACModelPermissionScope']:
        chain = [scope]
        chain.extend(RBACModelPermissionScopeModelService.get_ancestors(scope))
        return chain

    @staticmethod
    def get_inheritance_depth(scope) -> int:
        return len(RBACModelPermissionScopeModelService.get_ancestors(scope))

    @staticmethod
    def get_effective_fields(scope) -> Set[str]:
        """計算有效欄位：繼承父欄位 + 自己的欄位 - 排除欄位"""
        effective_fields = set()

        if scope.parent:
            effective_fields.update(
                RBACModelPermissionScopeModelService.get_effective_fields(scope.parent)
            )

        if scope.included_fields:
            effective_fields.update(scope.included_fields)

        if scope.excluded_fields:
            effective_fields -= set(scope.excluded_fields)

        return effective_fields

    @staticmethod
    def trace_field_source(scope, field_name: str) -> str:
        chain = RBACModelPermissionScopeModelService.get_inheritance_chain(scope)

        for s in chain:
            if field_name in (s.excluded_fields or []):
                return f"'{field_name}' 被 {s.name} 排除"

        for s in reversed(chain):
            if field_name in (s.included_fields or []):
                return f"'{field_name}' 來自 {s.name}"

        return f"'{field_name}' 不在此 scope 中"

    @staticmethod
    def get_children_recursive(scope) -> Set['RBACModelPermissionScope']:
        """獲取所有子孫 scope"""
        descendants = set()
        for child in scope.children.filter(is_active=True):
            descendants.add(child)
            descendants.update(
                RBACModelPermissionScopeModelService.get_children_recursive(child)
            )
        return descendants

    @staticmethod
    def validate_scope(scope):
        """驗證 scope 的繼承關係和欄位"""
        # 驗證繼承關係
        if scope.parent:
            # 防止循環繼承
            ancestors = RBACModelPermissionScopeModelService.get_ancestors(scope)
            if scope in ancestors:
                raise ValidationError('不能形成循環繼承')

            # 防止跨資源繼承 - 現在檢查 related_model 而非 context
            if scope.parent.related_model != scope.related_model:
                raise ValidationError('不能繼承不同 Model 的 Scope')

            # 限制繼承深度
            if len(ancestors) > 2:  # 最多3層 (自己 + 2層祖先)
                raise ValidationError('繼承深度不能超過3層')

        # 驗證欄位是否存在於模型中
        if scope.related_model:
            model_class = scope.related_model.model_class()
            if model_class:
                model_fields = {
                    f.name
                    for f in model_class._meta.fields
                    if not f.name.startswith('_') and not f.name.endswith('_id')
                }

                invalid_included = set(scope.included_fields or []) - model_fields
                if invalid_included:
                    raise ValidationError(
                        {
                            'included_fields': f"這些欄位不存在於 {model_class._meta.label} 模型中: {list(invalid_included)}"
                        }
                    )

                invalid_excluded = set(scope.excluded_fields or []) - model_fields
                if invalid_excluded:
                    raise ValidationError(
                        {
                            'excluded_fields': f"這些欄位不存在於 {model_class._meta.label} 模型中: {list(invalid_excluded)}"
                        }
                    )
