from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.authentication.models import PasswordResetToken
from apps.providers.models import ProviderProfile

User = get_user_model()
PW = "Str0ng-Passw0rd!"


def payload(phone="+919876543210", **extra):
    return {
        "phone": phone,
        "full_name": "Test User",
        "password": PW,
        "password_confirm": PW,
        **extra,
    }


class RegistrationTests(APITestCase):
    def test_customer_registration(self):
        res = self.client.post(reverse("register-customer"), payload(), format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["role"], "customer")
        self.assertNotIn("password", res.data)
        self.assertFalse(ProviderProfile.objects.exists())

    def test_provider_registration_creates_pending_profile(self):
        res = self.client.post(
            reverse("register-provider"),
            payload(business_name="Fix It Fast", email="provider@example.com"),
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["role"], "provider")
        profile = ProviderProfile.objects.get(user_id=res.data["id"])
        self.assertEqual(profile.approval_status, "pending")
        self.assertFalse(profile.is_available)
        self.assertEqual(profile.business_name, "Fix It Fast")

    def test_role_in_body_is_ignored(self):
        res = self.client.post(
            reverse("register-customer"), payload(role="admin", is_staff=True), format="json"
        )
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(pk=res.data["id"])
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_staff)

    def test_duplicate_phone_and_password_mismatch(self):
        self.client.post(reverse("register-customer"), payload(), format="json")
        dup = self.client.post(reverse("register-customer"), payload(), format="json")
        self.assertEqual(dup.status_code, 400)
        bad = payload(phone="+919000000001")
        bad["password_confirm"] = "different"
        res = self.client.post(reverse("register-customer"), bad, format="json")
        self.assertEqual(res.status_code, 400)

    def test_provider_registration_is_atomic(self):
        self.client.raise_request_exception = False
        with mock.patch(
            "apps.authentication.services.create_provider_profile",
            side_effect=RuntimeError("boom"),
        ):
            res = self.client.post(
                reverse("register-provider"),
                payload(email="provider@example.com"),
                format="json",
            )
        self.assertEqual(res.status_code, 500)
        self.assertFalse(User.objects.filter(phone="+919876543210").exists())

    def test_phone_is_normalized_and_duplicates_detected(self):
        res = self.client.post(
            reverse("register-customer"), payload(phone="98765 43210"), format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["phone"], "+919876543210")
        for variant in ["9876543210", "+91 98765-43210", "09876543210", "919876543210"]:
            dup = self.client.post(
                reverse("register-customer"), payload(phone=variant), format="json"
            )
            self.assertEqual(dup.status_code, 400, variant)
            self.assertIn("phone", dup.data)

    def test_invalid_phone_numbers_rejected(self):
        bad = [
            "98765432101",      # 11 digits
            "9876543210123",    # too long
            "987654321",        # 9 digits
            "5876543210",       # doesn't start with 6-9
            "+14155552671",     # not an Indian number
            "98765abcde",
            "",
        ]
        for phone in bad:
            res = self.client.post(
                reverse("register-customer"), payload(phone=phone), format="json"
            )
            self.assertEqual(res.status_code, 400, phone)
            self.assertIn("phone", res.data, phone)
        self.assertFalse(User.objects.exists())

    def test_email_is_trimmed_and_lowercased(self):
        res = self.client.post(
            reverse("register-customer"),
            payload(email="  Test.User@Example.COM "),
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["email"], "test.user@example.com")

    def test_duplicate_email_is_case_insensitive(self):
        self.client.post(
            reverse("register-customer"), payload(email="a@example.com"), format="json"
        )
        res = self.client.post(
            reverse("register-customer"),
            payload(phone="+919000000001", email="A@Example.com"),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)

    def test_invalid_emails_rejected(self):
        for email in ["not-an-email", "a@b", "a b@example.com", "@example.com", "a@@example.com"]:
            res = self.client.post(
                reverse("register-customer"), payload(email=email), format="json"
            )
            self.assertEqual(res.status_code, 400, email)
            self.assertIn("email", res.data, email)
        self.assertFalse(User.objects.exists())

    def test_email_is_optional_and_blank_emails_do_not_collide(self):
        # one user omits the email, another sends "", a third sends null
        for i, extra in enumerate([{}, {"email": ""}, {"email": None}]):
            res = self.client.post(
                reverse("register-customer"),
                payload(phone=f"+91900000000{i}", **extra),
                format="json",
            )
            self.assertEqual(res.status_code, 201, extra)
        self.assertEqual(User.objects.filter(email__isnull=True).count(), 3)

    def test_provider_must_supply_a_valid_email(self):
        cases = [
            {},                       # missing
            {"email": None},          # null
            {"email": ""},            # blank
            {"email": "not-an-email"},
        ]
        for extra in cases:
            res = self.client.post(
                reverse("register-provider"), payload(**extra), format="json"
            )
            self.assertEqual(res.status_code, 400, extra)
            self.assertIn("email", res.data, extra)
        self.assertFalse(User.objects.exists())
        self.assertFalse(ProviderProfile.objects.exists())

    def test_provider_email_is_normalized_and_unique_across_roles(self):
        self.client.post(
            reverse("register-customer"), payload(email="shared@example.com"), format="json"
        )
        dup = self.client.post(
            reverse("register-provider"),
            payload(phone="+919000000001", email="SHARED@example.com"),
            format="json",
        )
        self.assertEqual(dup.status_code, 400)
        self.assertIn("email", dup.data)
        ok = self.client.post(
            reverse("register-provider"),
            payload(phone="+919000000002", email=" New@Example.com "),
            format="json",
        )
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.data["email"], "new@example.com")

    def test_stale_token_does_not_block_registration(self):
        res = self.client.post(
            reverse("register-customer"),
            payload(),
            format="json",
            HTTP_AUTHORIZATION="Bearer expired.or.garbage",
        )
        self.assertEqual(res.status_code, 201)


class LoginAndProfileTests(APITestCase):
    def setUp(self):
        self.client.post(
            reverse("register-provider"),
            payload(email="provider@example.com"),
            format="json",
        )

    def login(self, **extra):
        return self.client.post(
            reverse("login"),
            {"phone": "+919876543210", "password": PW, **extra},
            format="json",
        )

    def test_login_returns_tokens_and_user(self):
        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertEqual(res.data["user"]["role"], "provider")

    def test_login_accepts_unformatted_phone(self):
        res = self.client.post(
            reverse("login"), {"phone": "98765 43210", "password": PW}, format="json"
        )
        self.assertEqual(res.status_code, 200)

    def test_wrong_password(self):
        res = self.client.post(
            reverse("login"), {"phone": "+919876543210", "password": "nope"}, format="json"
        )
        self.assertEqual(res.status_code, 401)

    def test_portal_mismatch_is_rejected(self):
        self.assertEqual(self.login(portal="customer").status_code, 403)
        self.assertEqual(self.login(portal="provider").status_code, 200)

    def test_profile_needs_token(self):
        self.assertEqual(self.client.get(reverse("profile")).status_code, 401)
        token = self.login().data["access"]
        res = self.client.get(reverse("profile"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["role"], "provider")


class LogoutTests(APITestCase):
    def setUp(self):
        self.client.post(reverse("register-customer"), payload(), format="json")

    def login(self):
        return self.client.post(
            reverse("login"), {"phone": "+919876543210", "password": PW}, format="json"
        ).data

    def refresh(self, token):
        return self.client.post(reverse("token-refresh"), {"refresh": token}, format="json")

    def test_logout_blacklists_refresh_token(self):
        tokens = self.login()
        self.assertEqual(self.refresh(tokens["refresh"]).status_code, 200)  # works before
        tokens = self.login()
        res = self.client.post(reverse("logout"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.refresh(tokens["refresh"]).status_code, 401)

    def test_logout_needs_no_access_token(self):
        tokens = self.login()
        res = self.client.post(
            reverse("logout"),
            {"refresh": tokens["refresh"]},
            format="json",
            HTTP_AUTHORIZATION="Bearer expired.garbage.token",
        )
        self.assertEqual(res.status_code, 204)

    def test_logout_rejects_bad_input_and_double_logout(self):
        tokens = self.login()
        self.assertEqual(self.client.post(reverse("logout"), {}, format="json").status_code, 400)
        bad = self.client.post(reverse("logout"), {"refresh": "garbage"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.client.post(reverse("logout"), {"refresh": tokens["refresh"]}, format="json")
        again = self.client.post(reverse("logout"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_refresh_rotates_and_old_token_is_rejected(self):
        old = self.login()["refresh"]
        res = self.refresh(old)
        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(res.data["refresh"], old)
        self.assertEqual(self.refresh(old).status_code, 401)       # old one is dead
        self.assertEqual(self.refresh(res.data["refresh"]).status_code, 200)

    def test_logout_all_revokes_every_device(self):
        phone_tokens = self.login()
        laptop_tokens = self.login()
        auth = {"HTTP_AUTHORIZATION": f"Bearer {phone_tokens['access']}"}
        res = self.client.post(reverse("logout-all"), format="json", **auth)
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.refresh(phone_tokens["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(laptop_tokens["refresh"]).status_code, 401)

    def test_logout_all_requires_authentication(self):
        self.assertEqual(self.client.post(reverse("logout-all")).status_code, 401)

    def test_deactivated_user_is_locked_out_immediately(self):
        tokens = self.login()
        auth = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}
        self.assertEqual(self.client.get(reverse("profile"), **auth).status_code, 200)
        User.objects.update(is_active=False)
        self.assertEqual(self.client.get(reverse("profile"), **auth).status_code, 401)


class PasswordResetTests(APITestCase):
    PHONE = "+919876543210"
    NEW_PW = "An0ther-Str0ng-Pw!"

    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.client.post(reverse("register-customer"), payload(), format="json")

    def request_code(self, phone=None):
        """Request a code; returns (response, otp or None)."""
        with mock.patch("apps.authentication.services.send_password_reset_otp") as sender:
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.post(
                    reverse("password-reset-request"),
                    {"phone": phone or self.PHONE},
                    format="json",
                )
        otp = sender.call_args.args[1] if sender.called else None
        return res, otp, sender

    def confirm(self, otp, new_password=None, **extra):
        pw = new_password or self.NEW_PW
        return self.client.post(
            reverse("password-reset-confirm"),
            {"phone": self.PHONE, "otp": otp, "new_password": pw, "new_password_confirm": pw, **extra},
            format="json",
        )

    def login(self, password):
        return self.client.post(
            reverse("login"), {"phone": self.PHONE, "password": password}, format="json"
        )

    def test_full_flow(self):
        res, otp, sender = self.request_code()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(sender.call_count, 1)
        self.assertRegex(otp, r"^\d{6}$")
        self.assertEqual(self.confirm(otp).status_code, 200)
        self.assertEqual(self.login(PW).status_code, 401)
        self.assertEqual(self.login(self.NEW_PW).status_code, 200)

    def test_unknown_number_gets_identical_response_and_no_code(self):
        known, _, _ = self.request_code()
        unknown, otp, sender = self.request_code("+919000000099")
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.data, known.data)
        self.assertFalse(sender.called)

    def test_inactive_user_gets_no_code(self):
        User.objects.update(is_active=False)
        res, otp, sender = self.request_code()
        self.assertEqual(res.status_code, 200)
        self.assertFalse(sender.called)

    def test_code_is_stored_hashed(self):
        _, otp, _ = self.request_code()
        token = PasswordResetToken.objects.get()
        self.assertNotIn(otp, token.token_hash)
        self.assertEqual(len(token.token_hash), 64)

    def test_wrong_code_counts_an_attempt_and_right_code_still_works(self):
        _, otp, _ = self.request_code()
        wrong = "000000" if otp != "000000" else "111111"
        self.assertEqual(self.confirm(wrong).status_code, 400)
        self.assertEqual(PasswordResetToken.objects.get().attempts, 1)  # committed, not rolled back
        self.assertEqual(self.confirm(otp).status_code, 200)

    def test_code_is_locked_after_max_attempts(self):
        _, otp, _ = self.request_code()
        wrong = "000000" if otp != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.confirm(wrong).status_code, 400)
        self.assertEqual(self.confirm(otp).status_code, 400)  # even the right code now fails
        self.assertEqual(self.login(PW).status_code, 200)     # password unchanged

    def test_expired_code_rejected(self):
        _, otp, _ = self.request_code()
        PasswordResetToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.confirm(otp).status_code, 400)

    def test_code_is_single_use(self):
        _, otp, _ = self.request_code()
        self.assertEqual(self.confirm(otp).status_code, 200)
        self.assertEqual(self.confirm(otp, new_password="Third-Str0ng-Pw!").status_code, 400)

    def test_weak_password_does_not_burn_the_code(self):
        _, otp, _ = self.request_code()
        res = self.confirm(otp, new_password="123")
        self.assertEqual(res.status_code, 400)
        self.assertIn("new_password", res.data)
        self.assertEqual(PasswordResetToken.objects.get().attempts, 0)
        self.assertEqual(self.confirm(otp).status_code, 200)

    def test_password_mismatch_rejected(self):
        _, otp, _ = self.request_code()
        res = self.confirm(otp, new_password_confirm="something-else")
        self.assertEqual(res.status_code, 400)
        self.assertIn("new_password_confirm", res.data)

    def test_malformed_code_rejected(self):
        self.request_code()
        for bad in ["12345", "1234567", "abcdef", ""]:
            self.assertEqual(self.confirm(bad).status_code, 400, bad)

    def test_resend_cooldown_and_newest_code_wins(self):
        _, first, sender = self.request_code()
        _, ignored, sender2 = self.request_code()          # within cooldown: ignored
        self.assertFalse(sender2.called)
        PasswordResetToken.objects.update(created_at=timezone.now() - timedelta(minutes=2))
        _, second, _ = self.request_code()
        self.assertIsNotNone(second)
        if second != first:
            self.assertEqual(self.confirm(first).status_code, 400)   # old code is dead
        self.assertEqual(self.confirm(second).status_code, 200)

    def test_reset_logs_out_existing_sessions(self):
        tokens = self.login(PW).data
        _, otp, _ = self.request_code()
        self.confirm(otp)
        res = self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_unknown_phone_confirm_gives_generic_error(self):
        res = self.client.post(
            reverse("password-reset-confirm"),
            {"phone": "+919000000099", "otp": "123456",
             "new_password": self.NEW_PW, "new_password_confirm": self.NEW_PW},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("otp", res.data)

    def test_request_endpoint_is_throttled_per_ip(self):
        codes = [self.request_code()[0].status_code for _ in range(6)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5], 429)