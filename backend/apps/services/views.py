from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, serializers, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny

from apps.locations.pagination import StandardPagination
from apps.locations.models import Area
from apps.locations.selectors import get_active_city
from apps.providers import selectors as provider_selectors
from apps.providers.serializers import PublicProviderOfferSerializer
from apps.users.permissions import IsAdminRole

from . import selectors
from .models import Category, Service
from .serializers import (
    AdminCategorySerializer,
    AdminServiceSerializer,
    CategoryPublicSerializer,
    ServiceDetailSerializer,
    ServicePublicSerializer,
)


def _bool_param(request, name):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return None
    return raw.lower() in ("1", "true", "yes")


def city_id_from_request(request):
    """Reads ?city=<id>. Returns None when absent; 400 when malformed or unknown."""
    raw = request.query_params.get("city")
    if raw in (None, ""):
        return None
    if not raw.isdigit():
        raise ValidationError({"city": "Must be a city id."})
    if get_active_city(int(raw)) is None:
        raise ValidationError({"city": "City not found."})
    return int(raw)


# ------------------------- public -------------------------
# authentication_classes = [] so a stale/expired token can't break open endpoints.

class _PublicMixin:
    permission_classes = [AllowAny]
    authentication_classes = []


class CategoryListView(_PublicMixin, generics.ListAPIView):
    """GET /categories/            -> active categories
    GET /categories/?city=<id>  -> only categories with a service available there"""

    serializer_class = CategoryPublicSerializer
    pagination_class = None

    def get_queryset(self):
        return selectors.list_categories(city_id=city_id_from_request(self.request))


class ServiceListView(_PublicMixin, generics.ListAPIView):
    """GET /?category=<id|slug>&city=<id>&search=<text>&page=&page_size="""

    serializer_class = ServicePublicSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        p = self.request.query_params
        return selectors.list_services(
            category=p.get("category"),
            city_id=city_id_from_request(self.request),
            search=p.get("search"),
        )


class ServiceDetailView(_PublicMixin, generics.RetrieveAPIView):
    """GET /<id>/[?city=<id>] -> adds available_in_city when a city is given"""

    serializer_class = ServiceDetailSerializer

    def get_queryset(self):
        return selectors.service_queryset()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["city_id"] = city_id_from_request(self.request)
        return context


def area_id_from_request(request, city_id):
    """Reads ?area=<id>. 400 when malformed/unknown, or when it is not in ?city=."""
    raw = request.query_params.get("area")
    if raw in (None, ""):
        return None
    if not raw.isdigit():
        raise ValidationError({"area": "Must be an area id."})
    area = Area.objects.filter(pk=int(raw), is_active=True, city__is_active=True).first()
    if area is None:
        raise ValidationError({"area": "Area not found."})
    if city_id is not None and area.city_id != city_id:
        raise ValidationError({"area": "This area is not in the selected city."})
    return area.pk


def scheduled_at_from_request(request):
    """Reads ?scheduled_at=2026-11-20T10:00:00+05:30 (a time without an offset is
    taken in the server's time zone). Must be in the future."""
    raw = request.query_params.get("scheduled_at")
    if not raw:
        return None
    try:
        value = serializers.DateTimeField().to_internal_value(raw)
    except serializers.ValidationError:
        raise ValidationError({"scheduled_at": "Use a date and time like 2026-11-20T10:00:00."})
    if value <= timezone.now():
        raise ValidationError({"scheduled_at": "Must be in the future."})
    return value


class ServiceProviderListView(_PublicMixin, generics.ListAPIView):
    """Who can do this job? GET /<service id>/providers/?city=&area=&scheduled_at=&ordering=

    With scheduled_at (the customer's chosen date and time) only providers who are
    free then are returned: the matching step before booking.
    ordering: price | -price | experience | -experience (default: online first, then cheapest)."""

    serializer_class = PublicProviderOfferSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        if not selectors.service_queryset().filter(pk=self.kwargs["pk"]).exists():
            raise NotFound("Service not found.")
        city_id = city_id_from_request(self.request)
        area_id = area_id_from_request(self.request, city_id)
        ordering = self.request.query_params.get("ordering")
        if ordering and ordering not in provider_selectors._OFFER_ORDERING:
            raise ValidationError({"ordering": f"Use one of {sorted(provider_selectors._OFFER_ORDERING)}."})
        return provider_selectors.offers_for_service(
            self.kwargs["pk"], city_id=city_id, area_id=area_id, ordering=ordering,
            available_at=scheduled_at_from_request(self.request),
        )


# ------------------------- admin portal -------------------------

class _ArchiveOnDeleteMixin:
    """DELETE archives (is_active=False) so bookings that reference the row keep working."""

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class AdminCategoryViewSet(_ArchiveOnDeleteMixin, viewsets.ModelViewSet):
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdminRole]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Category.objects.all()
        is_active = _bool_param(self.request, "is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs


class AdminServiceViewSet(_ArchiveOnDeleteMixin, viewsets.ModelViewSet):
    serializer_class = AdminServiceSerializer
    permission_classes = [IsAdminRole]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Service.objects.select_related("category")
        category = self.request.query_params.get("category")
        if category:
            if not category.isdigit():
                raise ValidationError({"category": "Must be a category id."})
            qs = qs.filter(category_id=int(category))
        is_active = _bool_param(self.request, "is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs
