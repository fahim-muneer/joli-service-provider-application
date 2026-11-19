from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AdminAreaViewSet, AdminCityViewSet, AreaListView, CityListView

router = SimpleRouter()
router.register("admin/cities", AdminCityViewSet, basename="admin-city")
router.register("admin/areas", AdminAreaViewSet, basename="admin-area")

urlpatterns = [
    path("cities/", CityListView.as_view(), name="city-list"),
    path("cities/<int:city_id>/areas/", AreaListView.as_view(), name="city-area-list"),
] + router.urls
