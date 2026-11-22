"""Read-only queries for bookings."""
from datetime import timedelta

from django.utils import timezone

from .models import Booking, BookingRequest


def provider_conflicts(provider_id, start, minutes, *, exclude_booking_id=None):
    """Accepted/in-progress bookings of this provider that overlap [start, start+minutes)."""
    end = start + timedelta(minutes=minutes)
    qs = Booking.objects.filter(
        assigned_provider_id=provider_id,
        status__in=Booking.ACTIVE_STATUSES,
        scheduled_at__lt=end,
        ends_at__gt=start,
    )
    return qs.exclude(pk=exclude_booking_id) if exclude_booking_id else qs


def _detail(qs):
    return qs.select_related("service", "customer", "assigned_provider", "assigned_provider__user").prefetch_related(
        "status_logs", "requests"
    )


# ---- customer ----

def list_customer_bookings(user, *, status=None):
    qs = Booking.objects.filter(customer=user).select_related("service", "assigned_provider", "assigned_provider__user")
    return qs.filter(status=status) if status else qs


def get_customer_booking(user, pk) -> Booking | None:
    return _detail(Booking.objects.filter(customer=user, pk=pk)).first()


# ---- provider ----

def list_provider_requests(provider):
    """Open offers this provider can still act on."""
    return (
        BookingRequest.objects.filter(provider=provider, status=BookingRequest.Status.OFFERED, expires_at__gt=timezone.now())
        .select_related("booking", "booking__service")
        .order_by("expires_at", "id")
    )


def get_provider_request(provider, pk) -> BookingRequest | None:
    return BookingRequest.objects.select_related("booking", "booking__service").filter(provider=provider, pk=pk).first()


def list_provider_bookings(provider, *, status=None):
    qs = Booking.objects.filter(assigned_provider=provider).select_related("service", "customer")
    return qs.filter(status=status) if status else qs


def get_provider_booking(provider, pk) -> Booking | None:
    return Booking.objects.select_related("service", "customer").filter(assigned_provider=provider, pk=pk).first()


# ---- admin ----

def list_all_bookings(*, status=None, search=None):
    from django.db.models import Q

    qs = Booking.objects.select_related("service", "customer", "assigned_provider", "assigned_provider__user")
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(reference__icontains=search) | Q(customer__phone__icontains=search)
            | Q(customer__full_name__icontains=search) | Q(service_name__icontains=search)
        )
    return qs


def get_booking_detail(pk) -> Booking | None:
    return _detail(Booking.objects.filter(pk=pk)).first()
