import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.providers.services import create_provider_profile

from .delivery import send_password_reset_otp
from .models import PasswordResetToken

User = get_user_model()

# Public sign-up can only ever create these roles. Admins come from createsuperuser.
PUBLIC_ROLES = {User.Role.CUSTOMER, User.Role.PROVIDER}


@transaction.atomic
def register_user(*, role, password, business_name=None, **user_fields):
    """Create the user, plus a pending ProviderProfile for providers.
    Both happen in one transaction: if the profile fails, the user is rolled back."""
    if role not in PUBLIC_ROLES:
        raise ValidationError({"role": "Invalid role."})

    user = User.objects.create_user(password=password, role=role, **user_fields)

    if role == User.Role.PROVIDER:
        create_provider_profile(user=user, business_name=business_name)

    return user


def revoke_all_sessions(user):
    """Blacklist every refresh token the user holds, i.e. log them out everywhere.
    Call this when an admin suspends a user or a user changes their password."""
    tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=t) for t in tokens], ignore_conflicts=True
    )


# ---------------------------------------------------------------------------
# Password reset (SMS one-time code)
# ---------------------------------------------------------------------------

OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = timedelta(seconds=60)


def _hash_otp(user_id, otp: str) -> str:
    """Keyed hash: a 6-digit code hashed with plain SHA-256 could be brute-forced
    offline if the table leaked; the SECRET_KEY makes that impossible."""
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{user_id}:{otp}".encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def request_password_reset(*, phone: str) -> None:
    """Create and send a reset code. Returns nothing and behaves the same whether
    or not the account exists, so callers cannot probe which numbers are registered."""
    user = User.objects.filter(phone=phone, is_active=True).first()
    if user is None:
        return

    now = timezone.now()
    latest = PasswordResetToken.objects.filter(user=user).order_by("-created_at").first()
    if latest and latest.created_at > now - OTP_RESEND_COOLDOWN:
        return  # too soon after the previous code; silently ignored

    # Only the newest code is ever valid.
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=now)

    otp = f"{secrets.randbelow(10**6):06d}"
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_otp(user.pk, otp),
        expires_at=now + OTP_TTL,
    )
    transaction.on_commit(lambda: send_password_reset_otp(user, otp))


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

    verified = False
    # Failed attempts must be COMMITTED even though we raise afterwards, so the
    # raise happens after this block, not inside it.
    with transaction.atomic():
        token = (
            PasswordResetToken.objects.select_for_update()
            .filter(user=user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if (
            token is None
            or token.expires_at <= timezone.now()
            or token.attempts >= OTP_MAX_ATTEMPTS
        ):
            pass
        elif hmac.compare_digest(token.token_hash, _hash_otp(user.pk, otp)):
            verified = True
            now = timezone.now()
            user.set_password(new_password)
            user.save(update_fields=["password"])
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
                used_at=now
            )
            revoke_all_sessions(user)  # log the user out everywhere
        else:
            token.attempts += 1
            token.save(update_fields=["attempts"])

    if not verified:
        raise invalid_code