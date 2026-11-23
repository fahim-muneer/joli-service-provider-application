import re
from datetime import date

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.models import Area, City
from apps.locations.pagination import StandardPagination
from apps.services.models import Service
from apps.providers import selectors as provider_selectors
from apps.users.permissions import HasVerifiedPhone, IsAdminRole, IsCustomerRole, IsProviderRole

from . import availability, selectors, services
from .models import Booking
from .serializers import (
    AdminBookingSerializer,
    BookingCreateSerializer,
    BookingListSerializer,
    BookingSerializer,
    CancelSerializer,
    CompleteSerializer,
    DeclineSerializer,
    ProviderBookingSerializer,
    ProviderRequestSerializer,
    StartSerializer,
    reasons_payload,
)


def _scope_param(request):
    value = request.query_params.get("scope")
    if value and value not in selectors.SCOPES:
        raise ValidationError({"scope": f"Must be one of {list(selectors.SCOPES)}."})
    return value or None


def _status_param(request):
    value = request.query_params.get("status")
    if value and value not in Booking.Status.values:
        raise ValidationError({"status": f"Must be one of {Booking.Status.values}."})
    return value or None


# =========================== customer ===========================

class BookingListCreateView(generics.ListAPIView):
    """GET my bookings: ?status= or ?scope=upcoming (soonest first) | history (latest first).
    POST creates a booking and offers it to matching providers (needs a verified phone number)."""

    serializer_class = BookingListSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomerRole(), HasVerifiedPhone()]
        return [IsCustomerRole()]

    def get_queryset(self):
        services.expire_stale_requests()
        return selectors.list_customer_bookings(
            self.request.user, status=_status_param(self.request), scope=_scope_param(self.request)
        )

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
        services.ensure_start_code(booking)
        return Response(BookingSerializer(booking).data)


class BookingCancelView(APIView):
    """Customer cancels with a reason (while requested or accepted)."""

    permission_classes = [IsCustomerRole]

    def post(self, request, pk):
        booking = selectors.get_customer_booking(request.user, pk)
        if booking is None:
            raise NotFound("Booking not found.")
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_booking(
            booking=booking, by=request.user, role="customer",
            reason_code=serializer.validated_data["reason_code"], note=serializer.validated_data["note"],
        )
        return Response(BookingSerializer(selectors.get_customer_booking(request.user, pk)).data)


class CancelReasonsView(APIView):
    """The reasons offered in the cancel popups, per role."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(reasons_payload())


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
    """Bookings I accepted: ?status= or ?scope=upcoming | history."""

    serializer_class = ProviderBookingSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return selectors.list_provider_bookings(
            self.get_profile(), status=_status_param(self.request), scope=_scope_param(self.request)
        )


class ProviderBookingDetailView(_ProviderView):
    def get(self, request, pk):
        booking = selectors.get_provider_booking(self.get_profile(), pk)
        if booking is None:
            raise NotFound("Booking not found.")
        return Response(ProviderBookingSerializer(booking).data)


class _ProviderBookingAction(_ProviderView):
    def get_booking(self, pk):
        booking = selectors.get_provider_booking(self.get_profile(), pk)
        if booking is None:
            raise NotFound("Booking not found.")
        return booking

    def respond(self, pk):
        return Response(ProviderBookingSerializer(selectors.get_provider_booking(self.get_profile(), pk)).data)


class ProviderBookingStartView(_ProviderBookingAction):
    """POST {"code": "123456"}: the customer's start code. accepted -> in_progress."""

    def post(self, request, pk):
        serializer = StartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.start_job(booking=self.get_booking(pk), provider=self.get_profile(), code=serializer.validated_data["code"])
        return self.respond(pk)


class ProviderBookingCompleteView(_ProviderBookingAction):
    """POST {"note": "..."} optional. in_progress -> completed."""

    def post(self, request, pk):
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.complete_job(booking=self.get_booking(pk), provider=self.get_profile(), note=serializer.validated_data["note"])
        return self.respond(pk)


class ProviderBookingCancelView(_ProviderBookingAction):
    """The provider withdraws from an accepted booking, with a reason."""

    def post(self, request, pk):
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_booking(
            booking=self.get_booking(pk), by=request.user, role="provider",
            reason_code=serializer.validated_data["reason_code"], note=serializer.validated_data["note"],
        )
        return self.respond(pk)


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


class AdminBookingCancelView(APIView):
    """Support can cancel any booking that is not finished, including one in progress."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        booking = selectors.get_booking_detail(pk)
        if booking is None:
            raise NotFound("Booking not found.")
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_booking(
            booking=booking, by=request.user, role="admin",
            reason_code=serializer.validated_data["reason_code"], note=serializer.validated_data["note"],
        )
        return Response(AdminBookingSerializer(selectors.get_booking_detail(pk)).data)


# =========================== availability (public: for the date picker) ===========================
# authentication_classes = [] so a stale token in the header can't break these open endpoints.

def _service_param(request):
    raw = request.query_params.get("service")
    if not raw or not raw.isdigit():
        raise ValidationError({"service": "Send the service id."})
    service = Service.objects.filter(pk=int(raw), is_active=True, category__is_active=True).first()
    if service is None:
        raise NotFound("Service not found.")
    return service


def _location_params(request):
    """?city=<id> and/or ?area=<id>. At least one is required: availability depends on where."""
    city_raw, area_raw = request.query_params.get("city"), request.query_params.get("area")
    if not city_raw and not area_raw:
        raise ValidationError({"detail": "Send city or area."})
    city_id = area_id = None
    if city_raw:
        if not city_raw.isdigit() or not City.objects.filter(pk=int(city_raw), is_active=True).exists():
            raise ValidationError({"city": "City not found."})
        city_id = int(city_raw)
    if area_raw:
        area = Area.objects.filter(pk=int(area_raw), is_active=True, city__is_active=True).first() if area_raw.isdigit() else None
        if area is None:
            raise ValidationError({"area": "Area not found."})
        if city_id is not None and area.city_id != city_id:
            raise ValidationError({"area": "This area is not in the selected city."})
        area_id = area.pk
    return city_id, area_id


class _PublicView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class AvailabilityCalendarView(_PublicView):
    """GET ?service=<id>&city=<id>|area=<id>&month=YYYY-MM (default: this month).
    One entry per day: status past | unavailable | limited | available, how many start
    times are free, and the price."""

    def get(self, request):
        service = _service_param(request)
        city_id, area_id = _location_params(request)
        today, last_bookable = availability.bookable_range()
        raw = request.query_params.get("month") or f"{today:%Y-%m}"
        match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", raw)
        if not match:
            raise ValidationError({"month": "Use the format YYYY-MM."})
        year, month = int(match.group(1)), int(match.group(2))
        if (year, month) < (today.year, today.month) or (year, month) > (last_bookable.year, last_bookable.month):
            raise ValidationError({"month": "Choose this month or one of the next few months."})
        return Response({
            "service": service.pk, "month": f"{year}-{month:02d}", "price": str(service.base_price), "currency": "INR",
            "days": availability.month_calendar(service, year, month, city_id=city_id, area_id=area_id),
        })


class DaySlotsView(_PublicView):
    """GET ?service=<id>&city=<id>|area=<id>&date=YYYY-MM-DD: the free start times of one day."""

    def get(self, request):
        service = _service_param(request)
        city_id, area_id = _location_params(request)
        raw = request.query_params.get("date")
        try:
            day = date.fromisoformat(raw or "")
        except ValueError:
            raise ValidationError({"date": "Use the format YYYY-MM-DD."})
        today, last_bookable = availability.bookable_range()
        if not today <= day <= last_bookable:
            raise ValidationError({"date": "Choose a date from today up to 90 days ahead."})
        return Response({
            "service": service.pk, "date": day.isoformat(), "price": str(service.base_price), "currency": "INR",
            "duration_minutes": service.estimated_duration_minutes,
            "slots": availability.day_slots(service, day, city_id=city_id, area_id=area_id),
        })