"""Read-only queries for providers, plus the availability rules.

A service is AVAILABLE IN A CITY when at least one provider
  - is approved,
  - has that service switched on (and the service + its category are active), and
  - covers at least one active area in that city.

(`ProviderProfile.is_available` is the provider's online/offline toggle. It is
for matching at booking time, so it deliberately does not hide catalogue items.)
"""
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from .models import (
    ProviderArea,
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
