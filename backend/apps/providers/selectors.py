"""Read-only queries for providers, plus the availability rules.

A service is AVAILABLE IN A CITY when at least one provider
  - is approved,
  - has that service switched on (and the service + its category are active), and
  - covers at least one active area in that city.

(`ProviderProfile.is_available` is the provider's online/offline toggle. It is
for matching at booking time, so it deliberately does not hide catalogue items.)
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from .models import (
    ProviderArea,
    ProviderAvailability,
    ProviderDocument,
    ProviderProfile,
    ProviderService,
)

Status = ProviderProfile.ApprovalStatus

# Documents a provider must have before they can submit for review / be approved.
REQUIRED_DOCUMENT_TYPES = (ProviderDocument.DocumentType.ID_PROOF,)
# Statuses from which a provider may (re)submit.
SUBMITTABLE_STATUSES = (Status.PENDING, Status.REJECTED)


# ------------------------- availability (customer catalogue) -------------------------

def live_provider_services():
    return ProviderService.objects.filter(
        is_active=True,
        service__is_active=True,
        service__category__is_active=True,
        provider__approval_status=Status.APPROVED,
    )


def available_service_ids(city_id):
    """Ids of services that can be booked in the city."""
    covers_city = ProviderArea.objects.filter(
        provider=OuterRef("provider"),
        area__city_id=city_id,
        area__is_active=True,
    )
    return live_provider_services().filter(Exists(covers_city)).values("service_id")


def served_city_ids():
    """Ids of cities where at least one live provider service can be delivered."""
    has_live_service = live_provider_services().filter(provider=OuterRef("provider"))
    return ProviderArea.objects.filter(
        Exists(has_live_service),
        area__is_active=True,
        area__city__is_active=True,
    ).values("area__city_id")


# ------------------------- provider self-service -------------------------

def get_provider_profile(user) -> ProviderProfile | None:
    return ProviderProfile.objects.select_related("user").filter(user=user).first()


def has_required_document(profile) -> bool:
    """An ID proof that is waiting for review or already approved."""
    return ProviderDocument.objects.filter(
        provider=profile,
        document_type__in=REQUIRED_DOCUMENT_TYPES,
        status__in=[ProviderDocument.Status.PENDING, ProviderDocument.Status.APPROVED],
    ).exists()


def has_approved_required_document(profile) -> bool:
    today = timezone.localdate()
    return ProviderDocument.objects.filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=today),
        provider=profile,
        document_type__in=REQUIRED_DOCUMENT_TYPES,
        status=ProviderDocument.Status.APPROVED,
    ).exists()


def submission_blockers(profile) -> list[str]:
    """What still stands between this provider and 'Submit for review'.
    Empty list = ready. Empty also when submitting makes no sense for the status."""
    if profile.approval_status not in SUBMITTABLE_STATUSES:
        return []
    blockers = []
    if not profile.user.is_phone_verified:
        blockers.append("Verify your phone number.")
    if not has_required_document(profile):
        blockers.append("Upload an ID proof.")
    return blockers


def can_submit(profile) -> bool:
    return profile.approval_status in SUBMITTABLE_STATUSES and not submission_blockers(profile)


def get_own_document(profile, pk) -> ProviderDocument | None:
    return ProviderDocument.objects.filter(provider=profile, pk=pk).first()


def list_own_documents(profile):
    return ProviderDocument.objects.filter(provider=profile)


def list_own_services(profile):
    return (
        ProviderService.objects.filter(provider=profile)
        .select_related("service", "service__category")
        .order_by("service__category__display_order", "service__name")
    )


def get_own_service(profile, pk) -> ProviderService | None:
    return list_own_services(profile).filter(pk=pk).first()


def list_own_areas(profile):
    return (
        ProviderArea.objects.filter(provider=profile)
        .select_related("area", "area__city")
        .order_by("area__city__name", "area__name")
    )


# ------------------------- admin portal -------------------------

def list_providers(*, status=None, search=None):
    qs = (
        ProviderProfile.objects.select_related("user")
        .annotate(
            documents_count=Count("documents", distinct=True),
            pending_documents_count=Count(
                "documents",
                filter=Q(documents__status=ProviderDocument.Status.PENDING),
                distinct=True,
            ),
        )
        .order_by("-applied_at", "-id")
    )
    if status:
        qs = qs.filter(approval_status=status)
    if search:
        qs = qs.filter(
            Q(user__full_name__icontains=search)
            | Q(user__phone__icontains=search)
            | Q(user__email__icontains=search)
            | Q(business_name__icontains=search)
        )
    return qs


def provider_detail_queryset():
    return ProviderProfile.objects.select_related("user", "reviewed_by").prefetch_related(
        "documents",
        "provider_services__service__category",
        "service_areas__area__city",
        "status_history__changed_by",
    )


# ------------------------- availability schedule -------------------------

def list_windows(profile, *, date_from=None, date_to=None):
    """The provider's windows from `date_from` (default: today) onward."""
    qs = ProviderAvailability.objects.filter(
        provider=profile, available_date__gte=date_from or timezone.localdate()
    )
    if date_to:
        qs = qs.filter(available_date__lte=date_to)
    return qs


def get_window(profile, pk) -> ProviderAvailability | None:
    return ProviderAvailability.objects.filter(provider=profile, pk=pk).first()


def overlapping_windows(profile, date, start, end, *, is_available, exclude_pk=None):
    """Windows of the same kind on that date that overlap [start, end)."""
    qs = ProviderAvailability.objects.filter(
        provider=profile,
        available_date=date,
        is_available=is_available,
        start_time__lt=end,
        end_time__gt=start,
    )
    return qs.exclude(pk=exclude_pk) if exclude_pk else qs


def window_fits(windows, start, minutes) -> bool:
    """`windows`: one provider's windows for the day of `start` (a naive local datetime).
    True if a working window fully contains the job and no blocked window touches it."""
    end = start + timedelta(minutes=minutes)
    if end.date() != start.date():
        return False  # no overnight jobs
    s, e = start.time(), end.time()
    if any((not w.is_available) and w.start_time < e and s < w.end_time for w in windows):
        return False
    return any(w.is_available and w.start_time <= s and e <= w.end_time for w in windows)


def to_local(dt):
    return timezone.localtime(dt) if timezone.is_aware(dt) else dt


def is_within_availability(profile, start_dt, minutes) -> bool:
    """Does this provider's SCHEDULE allow a job starting at `start_dt` and lasting `minutes`?
    Existing bookings are checked separately (bookings.selectors.provider_conflicts)."""
    start = to_local(start_dt)
    windows = list(
        ProviderAvailability.objects.filter(provider=profile, available_date=start.date())
    )
    return window_fits(windows, start, minutes)


def filter_offers_available_at(offers, start_dt):
    """Keep only the offers whose provider can do the job at `start_dt`: inside a working
    window (using each offer's own duration), clear of blocked time, and not already booked.
    Three queries however many providers there are; the queryset's ordering is preserved."""
    start = to_local(start_dt)
    rows = list(offers.values_list("pk", "provider_id", "estimated_duration_minutes"))
    windows = defaultdict(list)
    for w in ProviderAvailability.objects.filter(
        provider_id__in={provider_id for _, provider_id, _ in rows}, available_date=start.date()
    ):
        windows[w.provider_id].append(w)
    free = [(pk, provider_id, minutes) for pk, provider_id, minutes in rows if window_fits(windows[provider_id], start, minutes)]

    if free:
        # Imported here: bookings depends on providers, so providers must not import bookings at load time.
        from apps.bookings.models import Booking

        start_aware = start if timezone.is_aware(start) else timezone.make_aware(start)
        longest = max(minutes for _, _, minutes in free)
        busy = defaultdict(list)
        for provider_id, b_start, b_end in Booking.objects.filter(
            assigned_provider_id__in={provider_id for _, provider_id, _ in free},
            status__in=Booking.ACTIVE_STATUSES,
            scheduled_at__lt=start_aware + timedelta(minutes=longest),
            ends_at__gt=start_aware,
        ).values_list("assigned_provider_id", "scheduled_at", "ends_at"):
            busy[provider_id].append((b_start, b_end))
        free = [
            (pk, provider_id, minutes)
            for pk, provider_id, minutes in free
            if not any(b_start < start_aware + timedelta(minutes=minutes) and b_end > start_aware for b_start, b_end in busy[provider_id])
        ]
    return offers.filter(pk__in=[pk for pk, _, _ in free])


# ------------------------- customer-facing provider listing -------------------------

_OFFER_ORDERING = {
    "price": ["custom_price", "id"],
    "-price": ["-custom_price", "id"],
    "experience": ["provider__experience_years", "id"],
    "-experience": ["-provider__experience_years", "id"],
}
DEFAULT_OFFER_ORDERING = ["-provider__is_available", "custom_price", "id"]  # online first, cheapest first


def offers_for_service(service_id, *, city_id=None, area_id=None, ordering=None, available_at=None):
    """Live provider offers for one service, optionally limited to those who cover
    an area (or any area of a city) and, with `available_at`, to those who are free
    at that date and time. `ordering` must be a key of _OFFER_ORDERING."""
    qs = live_provider_services().filter(service_id=service_id).select_related("provider__user")
    if area_id is not None:
        qs = qs.filter(
            Exists(
                ProviderArea.objects.filter(
                    provider=OuterRef("provider"), area_id=area_id, area__is_active=True
                )
            )
        )
    elif city_id is not None:
        qs = qs.filter(
            Exists(
                ProviderArea.objects.filter(
                    provider=OuterRef("provider"), area__city_id=city_id, area__is_active=True
                )
            )
        )
    qs = qs.order_by(*(_OFFER_ORDERING.get(ordering) or DEFAULT_OFFER_ORDERING))
    if available_at is not None:
        qs = filter_offers_available_at(qs, available_at)
    return qs


def get_public_provider(pk) -> ProviderProfile | None:
    """An approved provider with only their live services and active areas attached."""
    return (
        ProviderProfile.objects.filter(pk=pk, approval_status=Status.APPROVED)
        .select_related("user")
        .prefetch_related(
            Prefetch(
                "provider_services",
                queryset=live_provider_services().select_related("service", "service__category"),
                to_attr="live_services",
            ),
            Prefetch(
                "service_areas",
                queryset=ProviderArea.objects.filter(
                    area__is_active=True, area__city__is_active=True
                ).select_related("area", "area__city"),
                to_attr="live_areas",
            ),
        )
        .first()
    )