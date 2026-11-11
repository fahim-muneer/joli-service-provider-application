import hashlib
import hmac
import math
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.providers.services import create_provider_profile

from .delivery import send_otp
from .models import OneTimeCode

User = get_user_model()
Purpose = OneTimeCode.Purpose

# Public sign-up can only ever create these roles. Admins come from createsuperuser.
PUBLIC_ROLES = {User.Role.CUSTOMER, User.Role.PROVIDER}

OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = timedelta(seconds=60)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@transaction.atomic
def register_user(*, role, password, business_name=None, **user_fields):
    """Create the user, plus a pending ProviderProfile for providers, and send the
    phone-verification code. All in one transaction: if anything fails, nothing
    is saved (and no SMS goes out, because sending happens after commit)."""
    if role not in PUBLIC_ROLES:
        raise ValidationError({"role": "Invalid role."})

    user = User.objects.create_user(password=password, role=role, **user_fields)

    if role == User.Role.PROVIDER:
        create_provider_profile(user=user, business_name=business_name)

    _issue_and_send(user, Purpose.PHONE_VERIFICATION)
    return user


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def revoke_all_sessions(user):
    """Blacklist every refresh token the user holds, i.e. log them out everywhere.
    Call this when an admin suspends a user or a user changes their password."""
    tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=t) for t in tokens], ignore_conflicts=True
    )


# ---------------------------------------------------------------------------
# One-time codes (shared by password reset and phone verification)
# ---------------------------------------------------------------------------

def _hash_otp(user_id, purpose: str, otp: str) -> str:
    """Keyed hash: a 6-digit code hashed with plain SHA-256 could be brute-forced
    offline if the table leaked; the SECRET_KEY makes that impossible. The purpose
    is part of the hash, so a code for one flow can never validate another."""
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{user_id}:{purpose}:{otp}".encode(), hashlib.sha256).hexdigest()


def _cooldown_remaining(user, purpose: str) -> int:
    """Seconds until another code may be requested (0 = allowed now)."""
    latest = (
        OneTimeCode.objects.filter(user=user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if latest is None:
        return 0
    remaining = latest.created_at + OTP_RESEND_COOLDOWN - timezone.now()
    return max(0, math.ceil(remaining.total_seconds()))


def _issue_and_send(user, purpose: str) -> None:
    """Invalidate older codes of this purpose, store a new one, and send it after
    the surrounding transaction commits."""
    now = timezone.now()
    OneTimeCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
        used_at=now
    )
    otp = f"{secrets.randbelow(10**6):06d}"
    OneTimeCode.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash_otp(user.pk, purpose, otp),
        expires_at=now + OTP_TTL,
    )
    transaction.on_commit(lambda: send_otp(user, otp, purpose))


def _consume_code(*, user, purpose: str, otp: str, on_success=None) -> bool:
    """Check a code. On success mark it used and run `on_success` in the same
    transaction. Returns True/False and never raises for a bad code.

    A failed attempt is COMMITTED (we return rather than raise inside the block),
    otherwise rolling back would erase the counter and allow brute-forcing."""
    with transaction.atomic():
        code = (
            OneTimeCode.objects.select_for_update()
            .filter(user=user, purpose=purpose, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if (
            code is None
            or code.expires_at <= timezone.now()
            or code.attempts >= OTP_MAX_ATTEMPTS
        ):
            return False

        if not hmac.compare_digest(code.code_hash, _hash_otp(user.pk, purpose, otp)):
            code.attempts += 1
            code.save(update_fields=["attempts"])
            return False

        OneTimeCode.objects.filter(
            user=user, purpose=purpose, used_at__isnull=True
        ).update(used_at=timezone.now())
        if on_success:
            on_success()
    return True


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

@transaction.atomic
def request_password_reset(*, phone: str) -> None:
    """Create and send a reset code. Returns nothing and behaves the same whether
    or not the account exists, so callers cannot probe which numbers are registered."""
    user = User.objects.filter(phone=phone, is_active=True).first()
    if user is None:
        return
    if _cooldown_remaining(user, Purpose.PASSWORD_RESET):
        return  # too soon after the previous code; silently ignored
    _issue_and_send(user, Purpose.PASSWORD_RESET)


def confirm_password_reset(*, phone: str, otp: str, new_password: str) -> None:
    invalid_code = ValidationError({"otp": "Invalid or expired code."})

    user = User.objects.filter(phone=phone, is_active=True).first()

    # Check password strength first, so a weak password never burns an attempt
    # or the code.
    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})

    if user is None:
        raise invalid_code

    def apply_new_password():
        user.set_password(new_password)
        user.save(update_fields=["password"])
        revoke_all_sessions(user)  # log the user out everywhere

    if not _consume_code(
        user=user, purpose=Purpose.PASSWORD_RESET, otp=otp, on_success=apply_new_password
    ):
        raise invalid_code


# ---------------------------------------------------------------------------
# Phone verification
# ---------------------------------------------------------------------------

def send_phone_verification(*, user) -> None:
    """(Re)send the verification code to the logged-in user."""
    if user.is_phone_verified:
        raise ValidationError({"detail": "Phone number is already verified."})
    wait = _cooldown_remaining(user, Purpose.PHONE_VERIFICATION)
    if wait:
        raise Throttled(wait=wait)
    with transaction.atomic():
        _issue_and_send(user, Purpose.PHONE_VERIFICATION)


def confirm_phone_verification(*, user, otp: str):
    if user.is_phone_verified:
        return user  # idempotent

    def mark_verified():
        user.is_phone_verified = True
        user.save(update_fields=["is_phone_verified"])

    if not _consume_code(
        user=user, purpose=Purpose.PHONE_VERIFICATION, otp=otp, on_success=mark_verified
    ):
        raise ValidationError({"otp": "Invalid or expired code."})
    return user


# ---------------------------------------------------------------------------
# Change password (logged-in user)
# ---------------------------------------------------------------------------

@transaction.atomic
def change_password(*, user, old_password: str, new_password: str) -> None:
    """Change the password and log the user out everywhere. The caller issues a
    fresh token pair afterwards so the current device stays signed in."""
    if not user.check_password(old_password):
        raise ValidationError({"old_password": "Incorrect password."})
    if old_password == new_password:
        raise ValidationError(
            {"new_password": "New password must be different from the current password."}
        )
    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)})

    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoke_all_sessions(user)