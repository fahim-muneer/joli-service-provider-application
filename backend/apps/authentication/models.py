from django.conf import settings
from django.db import models


class OneTimeCode(models.Model):
    """A short-lived SMS code. Only a keyed hash of the code is stored.

    One table serves every code-based flow; `purpose` keeps them separate."""

    class Purpose(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Password reset"
        PHONE_VERIFICATION = "phone_verification", "Phone verification"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="one_time_codes",
    )
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "one_time_codes"
        indexes = [models.Index(fields=["user", "purpose", "created_at"])]

    def __str__(self):
        return f"{self.purpose} code for user {self.user_id} ({self.created_at:%Y-%m-%d %H:%M})"