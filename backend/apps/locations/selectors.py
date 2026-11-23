"""Read-only queries for locations."""
from apps.providers import selectors as provider_selectors

from .models import City, CustomerAddress


def get_active_city(city_id) -> City | None:
    return City.objects.filter(pk=city_id, is_active=True).first()


def list_cities(*, available_only: bool = False):
    """Active cities. With available_only, just the cities where at least one
    approved provider offers a live service in an active area."""
    qs = City.objects.filter(is_active=True)
    if available_only:
        qs = qs.filter(pk__in=provider_selectors.served_city_ids())
    return qs


def list_areas(city: City):
    return city.areas.filter(is_active=True)


def list_addresses(user):
    return CustomerAddress.objects.filter(user=user, is_active=True).select_related(
        "area", "area__city"
    )


def get_address(user, pk) -> CustomerAddress | None:
    return list_addresses(user).filter(pk=pk).first()
