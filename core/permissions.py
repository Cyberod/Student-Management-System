from rest_framework.permissions import BasePermission

class IsAdminUserType(BasePermission):
    """
    Custom permission to allow only Admin users (user_type = 1).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 1)
    


class IsStaffUserType(BasePermission):
    """
    Custom permission to allow only Staff users (user_type = 2).
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 2)

class IsStaffOrAdmin(BasePermission):
    """
    Custom permission to allow Staff or Admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type in [1, 2])
    
