from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from apps.users.permissions import IsAdminRole

from . import selectors
from .models import Area, City
from .pagination import StandardPagination
from .serializers import (
    AdminAreaSerializer,
    AdminCitySerializer,
    AreaPublicSerializer,
    CityPublicSerializer,
)


def _bool_param(request, name):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return None
    return raw.lower() in ("1", "true", "yes")


# ------------------------- public -------------------------
# authentication_classes = [] so a stale/expired token in the header can't break
# these open endpoints.

class CityListView(generics.ListAPIView):
    """GET /cities/                 -> all active cities
    GET /cities/?available=true  -> only cities with live provider coverage"""

    serializer_class = CityPublicSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None

    def get_queryset(self):
        return selectors.list_cities(available_only=bool(_bool_param(self.request, "available")))


class AreaListView(generics.ListAPIView):
    """GET /cities/<id>/areas/ -> active areas of an active city"""

    serializer_class = AreaPublicSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None

    def get_queryset(self):
        city = get_object_or_404(City, pk=self.kwargs["city_id"], is_active=True)
        return selectors.list_areas(city)


# ------------------------- admin portal -------------------------

class _ArchiveOnDeleteMixin:
    """DELETE archives (is_active=False) instead of removing the row, so history
    that points at it (addresses, bookings, provider coverage) stays intact."""

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class AdminCityViewSet(_ArchiveOnDeleteMixin, viewsets.ModelViewSet):
    serializer_class = AdminCitySerializer
    permission_classes = [IsAdminRole]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = City.objects.all()
        is_active = _bool_param(self.request, "is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(state__icontains=search)
                | Q(district__icontains=search)
            )
        return qs


class AdminAreaViewSet(_ArchiveOnDeleteMixin, viewsets.ModelViewSet):
    serializer_class = AdminAreaSerializer
    permission_classes = [IsAdminRole]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Area.objects.select_related("city")
        city = self.request.query_params.get("city")
        if city:
            if not city.isdigit():
                raise ValidationError({"city": "Must be a city id."})
            qs = qs.filter(city_id=int(city))
        is_active = _bool_param(self.request, "is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(pincode__icontains=search))
        return qs
