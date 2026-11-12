from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from .permissions import HasVerifiedPhone, IsAdminRole, IsCustomerRole, IsProviderRole

User = get_user_model()
PW = "Str0ng-Passw0rd!"


def make_user(role, phone, verified=False):
    return User.objects.create_user(
        phone=phone, password=PW, full_name="Test", role=role, is_phone_verified=verified
    )


def allowed(permission_class, user):
    return permission_class().has_permission(SimpleNamespace(user=user), view=None)


class RolePermissionTests(TestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN, "+919111111111")
        self.provider = make_user(User.Role.PROVIDER, "+919222222222")
        self.customer = make_user(User.Role.CUSTOMER, "+919333333333")

    def test_each_permission_allows_only_its_own_role(self):
        matrix = {
            IsAdminRole: {self.admin: True, self.provider: False, self.customer: False},
            IsProviderRole: {self.admin: False, self.provider: True, self.customer: False},
            IsCustomerRole: {self.admin: False, self.provider: False, self.customer: True},
        }
        for permission, expectations in matrix.items():
            for user, expected in expectations.items():
                self.assertEqual(
                    allowed(permission, user), expected, f"{permission.__name__} / {user.role}"
                )

    def test_anonymous_is_denied_everywhere(self):
        anon = AnonymousUser()
        for permission in (IsAdminRole, IsProviderRole, IsCustomerRole, HasVerifiedPhone):
            self.assertFalse(allowed(permission, anon), permission.__name__)

    def test_verified_phone_permission(self):
        verified = make_user(User.Role.CUSTOMER, "+919444444444", verified=True)
        self.assertTrue(allowed(HasVerifiedPhone, verified))
        self.assertFalse(allowed(HasVerifiedPhone, self.customer))