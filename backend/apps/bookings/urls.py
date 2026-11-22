from django.urls import path

from . import views

urlpatterns = [
    # ---- customer ----
    path("", views.BookingListCreateView.as_view(), name="booking-list"),
    path("<int:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    # ---- provider ----
    path("provider/requests/", views.ProviderRequestListView.as_view(), name="provider-request-list"),
    path("provider/requests/<int:pk>/accept/", views.ProviderRequestAcceptView.as_view(), name="provider-request-accept"),
    path("provider/requests/<int:pk>/decline/", views.ProviderRequestDeclineView.as_view(), name="provider-request-decline"),
    path("provider/bookings/", views.ProviderBookingListView.as_view(), name="provider-booking-list"),
    path("provider/bookings/<int:pk>/", views.ProviderBookingDetailView.as_view(), name="provider-booking-detail"),
    # ---- admin ----
    path("admin/bookings/", views.AdminBookingListView.as_view(), name="admin-booking-list"),
    path("admin/bookings/<int:pk>/", views.AdminBookingDetailView.as_view(), name="admin-booking-detail"),
]
