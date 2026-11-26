
from django.conf import settings
from django.db import models


class Notification(models.Model):

    class Type(models.TextChoices):
        BOOKING_REQUEST = "booking_request", "New Booking Request"
        BOOKING_ACCEPTED = "booking_accepted", "Booking Accepted"
        BOOKING_DECLINED = "booking_declined", "Booking Declined"
        BOOKING_CANCELLED = "booking_cancelled", "Booking Cancelled"
        JOB_STARTED = "job_started", "Job Started"
        JOB_COMPLETED = "job_completed", "Job Completed"

        PROVIDER_APPROVED = "provider_approved", "Provider Approved"
        PROVIDER_REJECTED = "provider_rejected", "Provider Rejected"
        PROVIDER_SUSPENDED = "provider_suspended", "Provider Suspended"
        PROVIDER_REINSTATED = "provider_reinstated", "Provider Reinstated"

        SYSTEM = "system", "System Notification"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    type = models.CharField(
        max_length=60,
        choices=Type.choices,
    )

    title = models.CharField(max_length=150)

    body = models.CharField(max_length=500)

    is_read = models.BooleanField(default=False)

    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_read"],
                name="notification_user_read_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.user}"
