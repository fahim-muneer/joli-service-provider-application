from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission


class _HasRole(BasePermission):
    """Allow only authenticated users whose `role` matches `role_name`
    (the member name on the User.Role enum: ADMIN, PROVIDER or CUSTOMER)."""

    role_name = None

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.role == getattr(get_user_model().Role, self.role_name)


class IsAdminRole(_HasRole):
    role_name = "ADMIN"


class IsProviderRole(_HasRole):
    role_name = "PROVIDER"


class IsCustomerRole(_HasRole):
    role_name = "CUSTOMER"


class HasVerifiedPhone(BasePermission):
    """Combine with a role permission on actions that need a verified phone,
    e.g. permission_classes = [IsCustomerRole, HasVerifiedPhone]."""

    message = "Verify your phone number to continue."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_phone_verified)