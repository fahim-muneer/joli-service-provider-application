from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

User = get_user_model()
PW = "Str0ng-Passw0rd!"


def make_user(role, phone, **extra):
    return User.objects.create_user(phone=phone, password=PW, full_name="Original Name", role=role, **extra)


class ProfileUpdateTests(APITestCase):
    def setUp(self):
        self.url = reverse("profile")
        self.customer = make_user(User.Role.CUSTOMER, "+919300000001")
        self.provider = make_user(User.Role.PROVIDER, "+919300000002", email="prov@example.com")
        self.client.force_authenticate(self.customer)

    def test_requires_login(self):
        self.assertEqual(APIClient().patch(self.url, {"full_name": "X"}, format="json").status_code, 401)

    def test_change_name_and_email(self):
        res = self.client.patch(self.url, {"full_name": "  New Name ", "email": " New@Example.COM "}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["full_name"], "New Name")
        self.assertEqual(res.data["email"], "new@example.com")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "new@example.com")

    def test_partial_update_leaves_the_rest_alone(self):
        self.client.patch(self.url, {"email": "keep@example.com"}, format="json")
        res = self.client.patch(self.url, {"full_name": "Only Name"}, format="json")
        self.assertEqual((res.data["full_name"], res.data["email"]), ("Only Name", "keep@example.com"))

    def test_phone_and_role_cannot_be_changed_here(self):
        res = self.client.patch(
            self.url, {"full_name": "Same", "phone": "+919999999999", "role": "admin", "is_staff": True}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "+919300000001")
        self.assertEqual(self.customer.role, "customer")
        self.assertFalse(self.customer.is_staff)

    def test_resending_my_own_email_is_fine_but_someone_elses_is_not(self):
        self.client.patch(self.url, {"email": "mine@example.com"}, format="json")
        self.assertEqual(self.client.patch(self.url, {"email": "MINE@example.com"}, format="json").status_code, 200)
        res = self.client.patch(self.url, {"email": "PROV@example.com"}, format="json")  # the provider's, other case
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)

    def test_invalid_input(self):
        for bad in ({}, {"full_name": ""}, {"full_name": "x" * 151}, {"email": "not-an-email"}):
            self.assertEqual(self.client.patch(self.url, bad, format="json").status_code, 400, bad)

    def test_customer_may_remove_their_email_but_a_provider_may_not(self):
        self.client.patch(self.url, {"email": "gone@example.com"}, format="json")
        res = self.client.patch(self.url, {"email": ""}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["email"])

        self.client.force_authenticate(self.provider)
        for empty in ("", None):
            res = self.client.patch(self.url, {"email": empty}, format="json")
            self.assertEqual(res.status_code, 400, empty)
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.email, "prov@example.com")

    def test_get_still_works(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["full_name"], "Original Name")
