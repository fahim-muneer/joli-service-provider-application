from django.conf import settings
from django.db import models


class PasswordResetToken(models.Model):
    """One-time password-reset code sent by SMS. Only a keyed hash is stored."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_tokens"
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"reset token for user {self.user_id} ({self.created_at:%Y-%m-%d %H:%M})"