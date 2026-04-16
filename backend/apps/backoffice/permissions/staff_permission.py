from rest_framework.permissions import BasePermission


class IsStaffOrSuperuser(BasePermission):
    message = "Backoffice access is restricted to staff users."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
