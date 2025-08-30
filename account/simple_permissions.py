from rest_framework import permissions


class IsMember(permissions.BasePermission):
    """
    只允許 Member 用戶存取
    """

    message = '只有會員可以存取此資源'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return (
            hasattr(request.user, 'member_profile')
            and request.user.member_profile is not None
        )


class IsStaff(permissions.BasePermission):
    """
    只允許 Staff 用戶存取
    """

    message = '只有員工可以存取此資源'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return (
            hasattr(request.user, 'staff_profile')
            and request.user.staff_profile is not None
        )


class IsAdmin(permissions.BasePermission):
    """
    只允許 Admin Staff 用戶存取
    """

    message = '只有管理員可以存取此資源'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if not hasattr(request.user, 'staff_profile') or not request.user.staff_profile:
            return False

        return request.user.staff_profile.type == 'admin'
