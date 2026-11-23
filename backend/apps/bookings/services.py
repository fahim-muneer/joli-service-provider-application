"""Booking creation and the provider accept / decline flow."""
import hmac
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.providers import selectors as provider_selectors
from apps.providers.models import ProviderProfile, ProviderService

from . import selectors
from .exceptions import Conflict
from .models import (
    ADMIN_REASONS,
    CUSTOMER_REASONS,
    PROVIDER_REASONS,
    Booking,
    BookingRequest,
    BookingStatusLog,
    CancelReason,
)

MIN_LEAD = timedelta(hours=1)        # a booking must start at least this far ahead
MAX_DAYS_AHEAD = 90
MAX_OFFERS = 5                       # how many providers one booking is offered to
REQUEST_TTL = timedelta(minutes=30)  # how long a provider has to answer an offer
FREE_CANCEL_WINDOW = timedelta(hours=2)    # cancelling closer to the start than this is flagged "late"
START_OPENS_BEFORE = timedelta(minutes=60) # a provider may start a job this long before the booked time...
START_CLOSES_AFTER = timedelta(hours=6)    # ...and up to this long after it
MAX_START_ATTEMPTS = 5                     # wrong start codes allowed before the job is locked for support

Status = Booking.Status
ReqStatus = BookingRequest.Status


def new_start_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def ensure_start_code(booking) -> None:
    """Accepted bookings made before start codes existed get one the first time they are read."""
    if booking.status == Status.ACCEPTED and not booking.start_code:
        booking.start_code = new_start_code()
        booking.save(update_fields=["start_code", "updated_at"])


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
        booking.start_code = new_start_code()                   # the customer shows this to the provider on arrival
        booking.save(update_fields=["assigned_provider", "accepted_at", "duration_minutes", "ends_at", "start_code", "updated_at"])
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


# ---------------------------------------------------------------------------
# Life cycle after acceptance: cancel, start, complete
# ---------------------------------------------------------------------------

_ROLE_REASONS = {"customer": CUSTOMER_REASONS, "provider": PROVIDER_REASONS, "admin": ADMIN_REASONS}
# Which statuses each role may cancel from.
_CANCELLABLE = {
    "customer": {Status.REQUESTED, Status.ACCEPTED},
    "provider": {Status.ACCEPTED},                       # for a mere offer, decline it instead
    "admin": {Status.REQUESTED, Status.ACCEPTED, Status.IN_PROGRESS},
}


def cancel_booking(*, booking, by, role, reason_code, note="") -> Booking:
    """Cancel with a reason. The reason code must be one of the role's list; 'other' needs a note."""
    note = (note or "").strip()
    if reason_code not in _ROLE_REASONS[role]:
        raise ValidationError({"reason_code": "Choose one of the listed reasons."})
    if reason_code == CancelReason.OTHER and not note:
        raise ValidationError({"note": "Please describe the reason."})

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking.status not in _CANCELLABLE[role]:
            if booking.status == Status.IN_PROGRESS:
                raise ValidationError({"detail": "A job that has started cannot be cancelled here. Please contact support."})
            if booking.status == Status.REQUESTED and role == "provider":
                raise ValidationError({"detail": "Decline the request instead."})
            raise ValidationError({"detail": f"This booking is already {booking.status} and cannot be cancelled."})

        now = timezone.now()
        late = (
            role in ("customer", "provider")
            and booking.status == Status.ACCEPTED
            and booking.scheduled_at - now < FREE_CANCEL_WINDOW
        )
        booking.cancelled_at = now
        booking.cancelled_by = by
        booking.cancelled_by_role = role
        booking.cancellation_reason_code = reason_code
        booking.cancellation_note = note
        booking.cancelled_late = late
        booking.save(update_fields=[
            "cancelled_at", "cancelled_by", "cancelled_by_role", "cancellation_reason_code",
            "cancellation_note", "cancelled_late", "updated_at",
        ])
        label = CancelReason(reason_code).label
        _set_status(
            booking, Status.CANCELLED, by=by,
            remarks=f"Cancelled by the {role}: {label}." + (f" {note}" if note else "") + (" (late cancellation)" if late else ""),
        )
        booking.requests.filter(status=ReqStatus.OFFERED).update(status=ReqStatus.WITHDRAWN, responded_at=now)
        # TODO: notify the other party. Late-cancellation fees and provider penalties are decided with payments (Day 4).
        return booking


def start_window(booking):
    """(opens, closes): when the provider may start this job."""
    return booking.scheduled_at - START_OPENS_BEFORE, booking.scheduled_at + START_CLOSES_AFTER


def start_job(*, booking, provider, code) -> Booking:
    """accepted -> in_progress. Needs the code the customer sees. Wrong codes are counted and COMMITTED
    (we raise after the transaction ends), and after MAX_START_ATTEMPTS the job is locked for support."""
    outcome = "ok"
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking.assigned_provider_id != provider.pk:
            raise ValidationError({"detail": "This booking is not assigned to you."})
        if booking.status != Status.ACCEPTED:
            raise ValidationError({"detail": "Only an accepted booking can be started."})

        now = timezone.now()
        opens, closes = start_window(booking)
        if now < opens:
            raise ValidationError({"detail": f"You can start this job from {timezone.localtime(opens):%d %b %Y, %H:%M}."})
        if now > closes:
            raise ValidationError({"detail": "The start window has passed. Please contact support."})
        if booking.start_attempts >= MAX_START_ATTEMPTS:
            raise ValidationError({"detail": "Too many wrong codes. Please contact support."})

        if not booking.start_code:                              # a booking accepted before codes existed
            ensure_start_code(booking)
            outcome = "no_code"
        elif not hmac.compare_digest(booking.start_code, str(code)):
            booking.start_attempts += 1
            booking.save(update_fields=["start_attempts", "updated_at"])
            outcome = "wrong"
        else:
            booking.started_at = now
            booking.save(update_fields=["started_at", "updated_at"])
            _set_status(booking, Status.IN_PROGRESS, by=provider.user, remarks="Job started: the customer's code was entered.")

    if outcome == "no_code":
        raise ValidationError({"detail": "Ask the customer for the start code shown in their app, then try again."})
    if outcome == "wrong":
        left = MAX_START_ATTEMPTS - booking.start_attempts
        raise ValidationError({"code": f"That code is not correct. {left} attempt(s) left."})
    return booking


@transaction.atomic
def complete_job(*, booking, provider, note="") -> Booking:
    """in_progress -> completed. (The invoice is generated from this on Day 4.)"""
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.assigned_provider_id != provider.pk:
        raise ValidationError({"detail": "This booking is not assigned to you."})
    if booking.status != Status.IN_PROGRESS:
        raise ValidationError({"detail": "Only a job that has been started can be completed."})
    booking.completed_at = timezone.now()
    booking.save(update_fields=["completed_at", "updated_at"])
    _set_status(booking, Status.COMPLETED, by=provider.user, remarks=(note or "").strip() or "Job completed by the provider.")
    return booking