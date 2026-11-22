from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Booking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"        # offered to providers, waiting for one to accept
        ACCEPTED = "accepted", "Accepted"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"              # no provider accepted

    class PaymentMode(models.TextChoices):
        CASH = "cash", "Cash on delivery"
        ONLINE = "online", "Online payment"

    # Statuses in which the assigned provider's time is taken.
    ACTIVE_STATUSES = (Status.ACCEPTED, Status.IN_PROGRESS)

    reference = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT, related_name="bookings")
    address = models.ForeignKey("locations.CustomerAddress", on_delete=models.PROTECT, related_name="bookings")
    area = models.ForeignKey("locations.Area", on_delete=models.PROTECT, related_name="bookings")
    preferred_provider = models.ForeignKey(
        "providers.ProviderProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="preferred_bookings"
    )
    assigned_provider = models.ForeignKey(
        "providers.ProviderProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="bookings"
    )

    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    ends_at = models.DateTimeField()
    item_count = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(50)])
    customer_notes = models.TextField(blank=True)
    payment_mode = models.CharField(max_length=10, choices=PaymentMode.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED, db_index=True)

    # Snapshots: later edits to the service, price or address must not change an existing booking.
    service_name = models.CharField(max_length=120)
    pricing_type = models.CharField(max_length=12)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    address_snapshot = models.JSONField(default=dict)

    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"]),
            models.Index(fields=["assigned_provider", "scheduled_at", "status"]),
            models.Index(fields=["customer", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("scheduled_at")), name="booking_ends_after_start"),
            # a booking that is accepted (or beyond) always has a provider
            models.CheckConstraint(
                condition=~Q(status__in=["accepted", "in_progress", "completed"]) | Q(assigned_provider__isnull=False),
                name="booking_active_needs_provider",
            ),
        ]

    def __str__(self):
        return f"{self.reference or self.pk} ({self.status})"


class BookingRequest(models.Model):
    """One offer of a booking to one provider. The first provider to accept wins."""

    class Status(models.TextChoices):
        OFFERED = "offered", "Offered"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"
        WITHDRAWN = "withdrawn", "Withdrawn"    # someone else accepted

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="requests")
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.CASCADE, related_name="booking_requests")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFERED, db_index=True)
    offered_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True)

    class Meta:
        db_table = "booking_requests"
        ordering = ["-offered_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["booking", "provider"], name="uniq_request_per_provider")]
        indexes = [models.Index(fields=["provider", "status", "expires_at"])]

    def __str__(self):
        return f"request {self.pk}: booking {self.booking_id} -> provider {self.provider_id} ({self.status})"


class BookingStatusLog(models.Model):
    """Every status change of a booking, who made it and why (the booking history)."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="status_logs")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    remarks = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "booking_status_logs"
        ordering = ["changed_at", "id"]
