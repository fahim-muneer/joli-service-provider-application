from django.utils import timezone
from rest_framework import serializers

from apps.locations.models import CustomerAddress
from apps.providers.models import ProviderProfile
from apps.services.models import Service

from . import services as booking_services
from .models import (
    ADMIN_REASONS,
    CUSTOMER_REASONS,
    PROVIDER_REASONS,
    Booking,
    BookingRequest,
    BookingStatusLog,
    CancelReason,
)


def _cancellation(obj):
    """The cancellation details, or None when the booking was not cancelled."""
    if obj.status != Booking.Status.CANCELLED:
        return None
    return {
        "cancelled_at": obj.cancelled_at, "by": obj.cancelled_by_role,
        "reason_code": obj.cancellation_reason_code,
        "reason": CancelReason(obj.cancellation_reason_code).label if obj.cancellation_reason_code else "",
        "note": obj.cancellation_note, "late": obj.cancelled_late,
    }


def _display_name(provider):
    return provider.business_name or provider.user.full_name


class StatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingStatusLog
        fields = ["from_status", "to_status", "remarks", "changed_at"]
        read_only_fields = fields


# ------------------------- customer -------------------------

class BookingCreateSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.select_related("category"))
    address = serializers.PrimaryKeyRelatedField(queryset=CustomerAddress.objects.none())
    scheduled_at = serializers.DateTimeField()
    item_count = serializers.IntegerField(min_value=1, max_value=50, default=1)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    payment_mode = serializers.ChoiceField(choices=Booking.PaymentMode.choices)
    # Optional: a specific provider (the `provider` id from GET /services/<id>/providers/).
    provider = serializers.PrimaryKeyRelatedField(
        queryset=ProviderProfile.objects.select_related("user"), required=False, allow_null=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:  # only the customer's own, active addresses
            self.fields["address"].queryset = CustomerAddress.objects.filter(
                user=request.user, is_active=True
            ).select_related("area", "area__city")


class BookingSerializer(serializers.ModelSerializer):
    service = serializers.SerializerMethodField()
    address = serializers.JSONField(source="address_snapshot", read_only=True)
    provider = serializers.SerializerMethodField()
    pending_offers = serializers.SerializerMethodField()
    status_history = StatusLogSerializer(source="status_logs", many=True, read_only=True)
    start_code = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    free_cancellation_until = serializers.SerializerMethodField()
    cancellation = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "reference", "status", "service", "scheduled_at", "ends_at", "duration_minutes",
            "item_count", "customer_notes", "payment_mode", "unit_price", "discount_amount",
            "estimated_total", "currency", "address", "provider", "pending_offers",
            "start_code", "can_cancel", "free_cancellation_until", "cancellation",
            "accepted_at", "started_at", "completed_at", "created_at", "status_history",
        ]
        read_only_fields = fields

    def get_start_code(self, obj):
        """The customer shows this to the provider on arrival; it is only relevant until the job starts."""
        return obj.start_code if obj.status == Booking.Status.ACCEPTED else None

    def get_can_cancel(self, obj):
        return obj.status in (Booking.Status.REQUESTED, Booking.Status.ACCEPTED)

    def get_free_cancellation_until(self, obj):
        if obj.status != Booking.Status.ACCEPTED:
            return None
        return obj.scheduled_at - booking_services.FREE_CANCEL_WINDOW

    def get_cancellation(self, obj):
        return _cancellation(obj)

    def get_service(self, obj):
        return {"id": obj.service_id, "name": obj.service_name}

    def get_provider(self, obj):
        """Who is coming: only once a provider has accepted."""
        provider = obj.assigned_provider
        if provider is None:
            return None
        return {"id": provider.pk, "display_name": _display_name(provider), "phone": provider.user.phone}

    def get_pending_offers(self, obj):
        if obj.status != Booking.Status.REQUESTED:
            return 0
        return sum(1 for r in obj.requests.all() if r.status == BookingRequest.Status.OFFERED)


class BookingListSerializer(BookingSerializer):
    """The list view skips the per-booking history."""

    class Meta(BookingSerializer.Meta):
        fields = [f for f in BookingSerializer.Meta.fields if f != "status_history"]
        read_only_fields = fields


# ------------------------- provider -------------------------

class ProviderRequestSerializer(serializers.ModelSerializer):
    """An open offer. The customer's identity and exact address stay hidden until the provider accepts."""

    booking = serializers.SerializerMethodField()

    class Meta:
        model = BookingRequest
        fields = ["id", "status", "expires_at", "booking"]
        read_only_fields = fields

    def get_booking(self, obj):
        b = obj.booking
        snap = b.address_snapshot
        return {
            "reference": b.reference, "service": b.service_name, "scheduled_at": b.scheduled_at,
            "ends_at": b.ends_at, "duration_minutes": b.duration_minutes, "item_count": b.item_count,
            "notes": b.customer_notes, "payment_mode": b.payment_mode, "unit_price": str(b.unit_price),
            "estimated_total": str(b.estimated_total), "currency": b.currency,
            "area": snap.get("area"), "pincode": snap.get("pincode"), "city": snap.get("city"),
        }


class ProviderBookingSerializer(serializers.ModelSerializer):
    """A booking the provider has accepted: now the full address and customer contact are visible."""

    service = serializers.SerializerMethodField()
    address = serializers.JSONField(source="address_snapshot", read_only=True)
    customer = serializers.SerializerMethodField()
    status_history = StatusLogSerializer(source="status_logs", many=True, read_only=True)
    can_start = serializers.SerializerMethodField()
    start_opens_at = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    cancellation = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "reference", "status", "service", "scheduled_at", "ends_at", "duration_minutes",
            "item_count", "customer_notes", "payment_mode", "unit_price", "estimated_total", "currency",
            "address", "customer", "accepted_at", "started_at", "completed_at",
            "can_start", "start_opens_at", "can_cancel", "cancellation", "status_history",
        ]
        read_only_fields = fields   # note: the start code is never part of the provider's view

    def get_can_start(self, obj):
        if obj.status != Booking.Status.ACCEPTED:
            return False
        opens, closes = booking_services.start_window(obj)
        return opens <= timezone.now() <= closes

    def get_start_opens_at(self, obj):
        return booking_services.start_window(obj)[0] if obj.status == Booking.Status.ACCEPTED else None

    def get_can_cancel(self, obj):
        return obj.status == Booking.Status.ACCEPTED

    def get_cancellation(self, obj):
        return _cancellation(obj)

    def get_service(self, obj):
        return {"id": obj.service_id, "name": obj.service_name}

    def get_customer(self, obj):
        return {"name": obj.customer.full_name, "phone": obj.customer.phone}


# ------------------------- admin -------------------------

class AdminBookingSerializer(BookingSerializer):
    customer = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        # admins (support) see the start code even after the job has started
        fields = BookingSerializer.Meta.fields + ["customer", "offers", "start_attempts"]
        read_only_fields = fields

    def get_start_code(self, obj):
        return obj.start_code or None

    def get_customer(self, obj):
        return {"id": obj.customer_id, "name": obj.customer.full_name, "phone": obj.customer.phone}

    def get_offers(self, obj):
        return [
            {"provider": r.provider_id, "status": r.status, "offered_at": r.offered_at, "responded_at": r.responded_at,
             "decline_reason": r.decline_reason}
            for r in obj.requests.all()
        ]


class DeclineSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class CancelSerializer(serializers.Serializer):
    reason_code = serializers.ChoiceField(choices=CancelReason.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class StartSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code from the customer."})


class CompleteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


def reasons_payload():
    """For the cancel popups: the allowed reasons per role."""
    def as_list(codes):
        return [{"code": c.value, "label": c.label} for c in codes]

    return {
        "customer": as_list(CUSTOMER_REASONS),
        "provider": as_list(PROVIDER_REASONS),
        "admin": as_list(ADMIN_REASONS),
    }
