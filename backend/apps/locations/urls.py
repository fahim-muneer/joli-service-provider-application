from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AddressDefaultView,
    AddressDetailView,
    AddressListCreateView,
    AdminAreaViewSet,
    AdminCityViewSet,
    AreaListView,
    CityListView,
)

router = SimpleRouter()
router.register("admin/cities", AdminCityViewSet, basename="admin-city")
router.register("admin/areas", AdminAreaViewSet, basename="admin-area")

urlpatterns = [
    path("cities/", CityListView.as_view(), name="city-list"),
    path("cities/<int:city_id>/areas/", AreaListView.as_view(), name="city-area-list"),
    path("addresses/", AddressListCreateView.as_view(), name="address-list"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address-detail"),
    path("addresses/<int:pk>/default/", AddressDefaultView.as_view(), name="address-default"),
] + router.urls
