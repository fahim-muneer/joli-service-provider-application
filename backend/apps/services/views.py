from django.db.models import Q
from rest_framework import generics, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from apps.locations.pagination import StandardPagination
from apps.locations.selectors import get_active_city
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
