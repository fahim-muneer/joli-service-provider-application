import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp(user, otp: str, purpose: str) -> None:
    """Deliver a one-time code to the user's phone.

    `purpose` is "password_reset" or "phone_verification" (use it to pick the
    SMS wording).

    TODO: replace the body with a real SMS send through the notifications app
    (and a notification_deliveries row) once that exists.
    Until then the code is only printed to the server console in DEBUG.
    """
    if settings.DEBUG:
        logger.warning("[DEV ONLY] %s code for %s: %s", purpose, user.phone, otp)
    else:
        logger.error("SMS delivery is not configured; %s code for user %s not sent.", purpose, user.pk)