import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_password_reset_otp(user, otp: str) -> None:
    """Deliver the reset code to the user.

    TODO: replace the body with a real SMS send through the notifications app
    (and a notification_deliveries row) once that exists.
    Until then the code is only printed to the server console in DEBUG.
    """
    if settings.DEBUG:
        logger.warning("[DEV ONLY] Password reset code for %s: %s", user.phone, otp)
    else:
        logger.error("SMS delivery is not configured; reset code for user %s not sent.", user.pk)