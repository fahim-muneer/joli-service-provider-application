from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.pagination import StandardPagination
from apps.providers import selectors as provider_selectors
from apps.users.permissions import HasVerifiedPhone, IsAdminRole, IsCustomerRole, IsProviderRole

from . import selectors, services
from .models import Booking
from .serializers import (
    AdminBookingSerializer,
    BookingCreateSerializer,
    BookingListSerializer,
    BookingSerializer,
    DeclineSerializer,
    ProviderBookingSerializer,
    ProviderRequestSerializer,
)


def _status_param(request):
    value = request.query_params.get("status")
    if value and value not in Booking.Status.values:
        raise ValidationError({"status": f"Must be one of {Booking.Status.values}."})
    return value or None


# =========================== customer ===========================

class BookingListCreateView(generics.ListAPIView):
    """GET my bookings (?status=). POST creates a booking and offers it to matching providers.
    Creating needs a verified phone number."""

    serializer_class = BookingListSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomerRole(), HasVerifiedPhone()]
        return [IsCustomerRole()]

    def get_queryset(self):
        services.expire_stale_requests()
        return selectors.list_customer_bookings(self.request.user, status=_status_param(self.request))

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = services.create_booking(
            customer=request.user, service=data["service"], address=data["address"],
            scheduled_at=data["scheduled_at"], payment_mode=data["payment_mode"],
            item_count=data["item_count"], notes=data["notes"], preferred_provider=data.get("provider"),
        )
        booking = selectors.get_customer_booking(request.user, booking.pk)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingDetailView(APIView):
    permission_classes = [IsCustomerRole]

    def get(self, request, pk):
        booking = selectors.get_customer_booking(request.user, pk)
        if booking is None:
            raise NotFound("Booking not found.")
        services.expire_stale_requests(booking_id=booking.pk)
        booking = selectors.get_customer_booking(request.user, pk)
        return Response(BookingSerializer(booking).data)


# =========================== provider ===========================

class _ProviderView(APIView):
    permission_classes = [IsProviderRole]

    def get_profile(self):
        profile = provider_selectors.get_provider_profile(self.request.user)
        if profile is None:
            raise NotFound("This account has no provider profile.")
        return profile

    def get_offer(self, pk):
        offer = selectors.get_provider_request(self.get_profile(), pk)
        if offer is None:
            raise NotFound("Request not found.")
        return offer


class ProviderRequestListView(_ProviderView):
    """Open offers waiting for my answer (soonest to expire first)."""

    def get(self, request):
        profile = self.get_profile()
        services.expire_stale_requests()
        return Response(ProviderRequestSerializer(selectors.list_provider_requests(profile), many=True).data)


class ProviderRequestAcceptView(_ProviderView):
    def post(self, request, pk):
        profile = self.get_profile()
        booking = services.accept_request(booking_request=self.get_offer(pk), provider=profile)
        return Response(ProviderBookingSerializer(selectors.get_provider_booking(profile, booking.pk)).data)


class ProviderRequestDeclineView(_ProviderView):
    def post(self, request, pk):
        serializer = DeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer = services.decline_request(
            booking_request=self.get_offer(pk), provider=self.get_profile(), reason=serializer.validated_data["reason"]
        )
        return Response(ProviderRequestSerializer(offer).data)


class ProviderBookingListView(_ProviderView, generics.ListAPIView):
    """Bookings I accepted (?status=)."""

    serializer_class = ProviderBookingSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return selectors.list_provider_bookings(self.get_profile(), status=_status_param(self.request))


class ProviderBookingDetailView(_ProviderView):
    def get(self, request, pk):
        booking = selectors.get_provider_booking(self.get_profile(), pk)
        if booking is None:
            raise NotFound("Booking not found.")
        return Response(ProviderBookingSerializer(booking).data)


# =========================== admin ===========================

class AdminBookingListView(generics.ListAPIView):
    serializer_class = AdminBookingSerializer
    permission_classes = [IsAdminRole]
    pagination_class = StandardPagination

    def get_queryset(self):
        return selectors.list_all_bookings(
            status=_status_param(self.request), search=self.request.query_params.get("search")
        ).prefetch_related("status_logs", "requests")


class AdminBookingDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, pk):
        booking = selectors.get_booking_detail(pk)
        if booking is None:
            raise NotFound("Booking not found.")
        return Response(AdminBookingSerializer(booking).data)
