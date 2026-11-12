from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminCategoryViewSet,
    AdminServiceViewSet,
    CategoryListView,
    ServiceDetailView,
    ServiceListView,
)

router = SimpleRouter()
router.register("admin/categories", AdminCategoryViewSet, basename="admin-category")
router.register("admin/services", AdminServiceViewSet, basename="admin-service")

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("<int:pk>/", ServiceDetailView.as_view(), name="service-detail"),
    path("", ServiceListView.as_view(), name="service-list"),
] + router.urls
