"""Booking creation and the provider accept / decline flow."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.providers import selectors as provider_selectors
from apps.providers.models import ProviderProfile, ProviderService

from . import selectors
from .exceptions import Conflict
from .models import Booking, BookingRequest, BookingStatusLog

MIN_LEAD = timedelta(hours=1)        # a booking must start at least this far ahead
MAX_DAYS_AHEAD = 90
MAX_OFFERS = 5                       # how many providers one booking is offered to
REQUEST_TTL = timedelta(minutes=30)  # how long a provider has to answer an offer

Status = Booking.Status
ReqStatus = BookingRequest.Status


def _log(booking, to_status, *, by=None, remarks="", from_status=""):
    BookingStatusLog.objects.create(
        booking=booking, changed_by=by, from_status=from_status, to_status=to_status, remarks=remarks
    )


def _set_status(booking, to_status, *, by=None, remarks=""):
    old = booking.status
    booking.status = to_status
    booking.save(update_fields=["status", "updated_at"])
    _log(booking, to_status, by=by, remarks=remarks, from_status=old)


def _address_snapshot(address) -> dict:
    area = address.area
    return {
        "label": address.label,
        "address_line": address.address_line,
        "landmark": address.landmark,
        "latitude": str(address.latitude) if address.latitude is not None else None,
        "longitude": str(address.longitude) if address.longitude is not None else None,
        "area": area.name,
        "pincode": area.pincode,
        "city": area.city.name,
    }


@transaction.atomic
def create_booking(
    *, customer, service, address, scheduled_at, payment_mode, item_count=1, notes="", preferred_provider=None
) -> Booking:
    """Create a booking and offer it to matching providers.

    Pricing: a booking offered to several providers is quoted at the catalogue price
    (the customer must know the price before anyone accepts). A booking for one chosen
    provider is quoted at that provider's own price."""
    now = timezone.now()
    if scheduled_at < now + MIN_LEAD:
        raise ValidationError({"scheduled_at": "Choose a time at least 1 hour from now."})
    if scheduled_at > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError({"scheduled_at": f"Bookings can be made up to {MAX_DAYS_AHEAD} days ahead."})
    if not (service.is_active and service.category.is_active):
        raise ValidationError({"service": "This service is not available."})

    area = address.area
    if not provider_selectors.available_service_ids(area.city_id).filter(service_id=service.pk).exists():
        raise ValidationError({"service": "This service is not available in your city yet."})

    offers = list(provider_selectors.offers_for_service(service.pk, area_id=area.pk, available_at=scheduled_at))
    if preferred_provider is not None:
        offers = [o for o in offers if o.provider_id == preferred_provider.pk]
        if not offers:
            raise ValidationError({"provider": "This provider is not available at that time."})
        unit_price, duration = offers[0].custom_price, offers[0].estimated_duration_minutes
    else:
        if not offers:
            raise ValidationError({"scheduled_at": "No provider is available at that time. Please choose another time."})
        offers = offers[:MAX_OFFERS]  # already ordered: online first, then cheapest
        unit_price, duration = service.base_price, service.estimated_duration_minutes

    booking = Booking.objects.create(
        customer=customer, service=service, address=address, area=area,
        preferred_provider=preferred_provider,
        scheduled_at=scheduled_at, duration_minutes=duration, ends_at=scheduled_at + timedelta(minutes=duration),
        item_count=item_count, customer_notes=notes, payment_mode=payment_mode,
        service_name=service.name, pricing_type=service.pricing_type, unit_price=unit_price,
        estimated_total=(Decimal(unit_price) * item_count).quantize(Decimal("0.01")),
        address_snapshot=_address_snapshot(address),
    )
    booking.reference = f"JB{booking.pk:07d}"
    booking.save(update_fields=["reference"])

    expires_at = now + REQUEST_TTL
    BookingRequest.objects.bulk_create(
        [BookingRequest(booking=booking, provider_id=o.provider_id, expires_at=expires_at) for o in offers]
    )
    _log(booking, Status.REQUESTED, by=customer, remarks=f"Booking created and offered to {len(offers)} provider(s).")
    # TODO: notify each provider (SMS / in-app) through the notifications app, via transaction.on_commit.
    return booking


@transaction.atomic
def expire_stale_requests(*, booking_id=None, now=None) -> int:
    """Offers nobody answered in time become 'expired'; a booking with no open offers
    left becomes 'expired' too. Safe to run any time (also exposed as a management command)."""
    now = now or timezone.now()
    stale = BookingRequest.objects.filter(status=ReqStatus.OFFERED, expires_at__lte=now)
    if booking_id:
        stale = stale.filter(booking_id=booking_id)
    booking_ids = list(stale.values_list("booking_id", flat=True).distinct())
    count = stale.update(status=ReqStatus.EXPIRED, responded_at=now)
    for booking in Booking.objects.select_for_update().filter(pk__in=booking_ids, status=Status.REQUESTED):
        if not booking.requests.filter(status=ReqStatus.OFFERED).exists():
            _set_status(booking, Status.EXPIRED, remarks="No provider accepted in time.")
    return count


def _require_open_offer(booking_request, provider, booking):
    """The offer must belong to this provider and still be open. Each way it can fail has its own message."""
    if booking_request.provider_id != provider.pk:
        raise ValidationError({"detail": "This request belongs to another provider."})
    if booking_request.status == ReqStatus.EXPIRED or booking.status == Status.EXPIRED:
        raise ValidationError({"detail": "This offer has expired."})
    if booking.status == Status.CANCELLED:
        raise ValidationError({"detail": "This booking was cancelled."})
    if booking.assigned_provider_id == provider.pk:
        raise ValidationError({"detail": "You have already accepted this booking."})
    if booking.status != Status.REQUESTED:
        raise Conflict("This booking was already taken by another provider.")
    if booking_request.status != ReqStatus.OFFERED:
        raise ValidationError({"detail": f"This request is already {booking_request.status}."})


def accept_request(*, booking_request, provider) -> Booking:
    """Accept an offer. Exactly one provider can win: the booking row is locked, the
    status is re-checked, and every other open offer is withdrawn in the same transaction."""
    expire_stale_requests(booking_id=booking_request.booking_id)  # commit expiry BEFORE any check can raise

    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related("service").get(pk=booking_request.booking_id)
        booking_request = BookingRequest.objects.select_for_update().get(pk=booking_request.pk)
        _require_open_offer(booking_request, provider, booking)

        if provider.approval_status != ProviderProfile.ApprovalStatus.APPROVED:
            raise PermissionDenied("Your account is not approved to accept jobs.")

        offer = ProviderService.objects.filter(provider=provider, service=booking.service, is_active=True).first()
        minutes = offer.estimated_duration_minutes if offer else booking.duration_minutes
        if not provider_selectors.is_within_availability(provider, booking.scheduled_at, minutes):
            raise ValidationError({"detail": "You are not available at this time. Update your schedule first."})
        if selectors.provider_conflicts(provider.pk, booking.scheduled_at, minutes, exclude_booking_id=booking.pk).exists():
            raise ValidationError({"detail": "You already have a booking that overlaps this time."})

        now = timezone.now()
        booking.assigned_provider = provider
        booking.accepted_at = now
        booking.duration_minutes = minutes                      # the accepting provider's own duration
        booking.ends_at = booking.scheduled_at + timedelta(minutes=minutes)
        booking.save(update_fields=["assigned_provider", "accepted_at", "duration_minutes", "ends_at", "updated_at"])
        _set_status(booking, Status.ACCEPTED, by=provider.user, remarks="Accepted by the provider.")

        booking_request.status = ReqStatus.ACCEPTED
        booking_request.responded_at = now
        booking_request.save(update_fields=["status", "responded_at"])
        booking.requests.filter(status=ReqStatus.OFFERED).exclude(pk=booking_request.pk).update(
            status=ReqStatus.WITHDRAWN, responded_at=now
        )
        # TODO: notify the customer that a provider accepted.
        return booking


def decline_request(*, booking_request, provider, reason="") -> BookingRequest:
    expire_stale_requests(booking_id=booking_request.booking_id)

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking_request.booking_id)
        booking_request = BookingRequest.objects.select_for_update().get(pk=booking_request.pk)
        _require_open_offer(booking_request, provider, booking)

        booking_request.status = ReqStatus.DECLINED
        booking_request.responded_at = timezone.now()
        booking_request.decline_reason = (reason or "").strip()
        booking_request.save(update_fields=["status", "responded_at", "decline_reason"])
        if not booking.requests.filter(status=ReqStatus.OFFERED).exists():
            _set_status(booking, Status.EXPIRED, remarks="Every provider declined or did not answer.")
            # TODO: tell the customer to pick another time.
        return booking_request
