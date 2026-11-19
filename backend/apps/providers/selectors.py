"""Availability rules: what can customers actually book, and where?

A service is AVAILABLE IN A CITY when at least one provider
  - is approved,
  - has that service switched on (and the service + its category are active), and
  - covers at least one active area in that city.

(`ProviderProfile.is_available` is the provider's online/offline toggle. It is
for matching at booking time, so it deliberately does not hide catalogue items.)
"""
from django.db.models import Exists, OuterRef

from .models import ProviderArea, ProviderProfile, ProviderService


def live_provider_services():
    return ProviderService.objects.filter(
        is_active=True,
        service__is_active=True,
        service__category__is_active=True,
        provider__approval_status=ProviderProfile.ApprovalStatus.APPROVED,
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
