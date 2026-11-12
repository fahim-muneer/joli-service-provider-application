"""Read-only queries for the service catalogue."""
from django.db.models import Exists, OuterRef, Q

from apps.providers import selectors as provider_selectors

from .models import Category, Service


def list_categories(*, city_id=None):
    """Active categories. With a city, only those that have at least one service
    available there."""
    qs = Category.objects.filter(is_active=True)
    if city_id is not None:
        in_city = Service.objects.filter(
            category=OuterRef("pk"),
            is_active=True,
            pk__in=provider_selectors.available_service_ids(city_id),
        )
        qs = qs.filter(Exists(in_city))
    return qs


def service_queryset():
    return Service.objects.filter(is_active=True, category__is_active=True).select_related(
        "category"
    )


def list_services(*, category=None, city_id=None, search=None):
    qs = service_queryset()
    if category:
        qs = (
            qs.filter(category_id=int(category))
            if str(category).isdigit()
            else qs.filter(category__slug=category)
        )
    if city_id is not None:
        qs = qs.filter(pk__in=provider_selectors.available_service_ids(city_id))
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(category__name__icontains=search)
        )
    return qs
