from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Area, City, CustomerAddress
from apps.providers.factories import cover, make_provider, offer
from apps.providers.models import ProviderAvailability, ProviderProfile
from apps.services.models import Category, Service

from .models import Booking, BookingRequest, BookingStatusLog
from .services import MAX_OFFERS, REQUEST_TTL

User = get_user_model()
PW = "Str0ng-Passw0rd!"
Status = ProviderProfile.ApprovalStatus


def day(n):
    return timezone.localdate() + timedelta(days=n)


def at(n, hour, minute=0):
    return timezone.make_aware(datetime.combine(day(n), datetime.min.time()).replace(hour=hour, minute=minute))


def make_user(role, phone, verified=True):
    return User.objects.create_user(phone=phone, password=PW, full_name="Test User", role=role, is_phone_verified=verified)


class BookingTestCase(APITestCase):
    def setUp(self):
        self.city = City.objects.create(name="Bengaluru", state="Karnataka")
        self.area = Area.objects.create(city=self.city, name="Indiranagar", pincode="560038")
        self.service = Service.objects.create(
            category=Category.objects.create(name="Plumbing"), name="Tap repair",
            base_price=Decimal("500.00"), estimated_duration_minutes=60,
        )
        self.customer = make_user(User.Role.CUSTOMER, "+919820000001")
        self.address = CustomerAddress.objects.create(
            user=self.customer, area=self.area, label="Home", address_line="12 Test Street, Block A",
            landmark="Near the park", is_default=True,
        )
        self.admin = make_user(User.Role.ADMIN, "+919820000099")
        self.anita = self.provider("+919830000001", "Anita", "400", online=True)
        self.bala = self.provider("+919830000002", "Bala", "450")
        self.client.force_authenticate(self.customer)

    # ---- helpers ----
    def provider(self, phone, name, price, *, online=False, minutes=None, window=True, approved=True):
        profile = make_provider(
            phone, business_name=name, email=f"{name.lower()}@example.com", phone_verified=True,
            status=Status.APPROVED if approved else Status.PENDING,
        )
        offer(profile, self.service, price=Decimal(price))
        if minutes:
            profile.provider_services.update(estimated_duration_minutes=minutes)
        cover(profile, self.area)
        if window:
            ProviderAvailability.objects.create(provider=profile, available_date=day(2), start_time="09:00", end_time="17:00")
        if online:
            ProviderProfile.objects.filter(pk=profile.pk).update(is_available=True)
        return profile

    def body(self, **extra):
        return {
            "service": self.service.pk, "address": self.address.pk, "scheduled_at": at(2, 10).isoformat(),
            "item_count": 1, "payment_mode": "cash", **extra,
        }

    def book(self, **extra):
        return self.client.post(reverse("booking-list"), self.body(**extra), format="json")

    def as_user(self, user):
        self.client = APIClient()
        self.client.force_authenticate(user)

    def offer_for(self, provider, booking_id=None):
        qs = BookingRequest.objects.filter(provider=provider)
        return qs.get(booking_id=booking_id) if booking_id else qs.get()

    def accept(self, provider, offer_obj):
        self.as_user(provider.user)
        return self.client.post(reverse("provider-request-accept", args=[offer_obj.pk]))

    def decline(self, provider, offer_obj, **body):
        self.as_user(provider.user)
        return self.client.post(reverse("provider-request-decline", args=[offer_obj.pk]), body, format="json")


class CreateBookingTests(BookingTestCase):
    def test_creating_a_booking_offers_it_to_matching_providers(self):
        res = self.book(item_count=2, notes="Please bring a ladder")
        self.assertEqual(res.status_code, 201, res.data)
        data = res.data
        self.assertEqual((data["status"], data["pending_offers"], data["provider"]), ("requested", 2, None))
        self.assertRegex(data["reference"], r"^JB\d{7}$")
        self.assertEqual((data["unit_price"], data["estimated_total"], data["currency"]), ("500.00", "1000.00", "INR"))
        self.assertEqual((data["item_count"], data["customer_notes"], data["payment_mode"]), (2, "Please bring a ladder", "cash"))
        self.assertEqual((data["duration_minutes"], data["service"]["name"]), (60, "Tap repair"))
        self.assertEqual(data["address"]["address_line"], "12 Test Street, Block A")
        self.assertEqual(data["address"]["city"], "Bengaluru")
        self.assertEqual(len(data["status_history"]), 1)

        booking = Booking.objects.get()
        self.assertEqual(booking.requests.count(), 2)
        self.assertEqual(set(booking.requests.values_list("provider_id", flat=True)), {self.anita.pk, self.bala.pk})
        expires = booking.requests.first().expires_at
        self.assertAlmostEqual((expires - timezone.now()).total_seconds(), REQUEST_TTL.total_seconds(), delta=30)

    def test_response_never_names_the_offered_providers(self):
        res = self.book()
        self.assertNotIn("Anita", str(res.data))
        self.assertNotIn("+919830000001", str(res.data))

    def test_booking_for_a_chosen_provider_uses_their_price_and_only_they_are_asked(self):
        res = self.book(provider=self.bala.pk)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["unit_price"], res.data["pending_offers"]), ("450.00", 1))
        self.assertEqual(list(Booking.objects.get().requests.values_list("provider_id", flat=True)), [self.bala.pk])

    def test_chosen_provider_who_is_not_available_is_refused(self):
        busy = self.provider("+919830000003", "Chitra", "300", window=False)
        res = self.book(provider=busy.pk)
        self.assertEqual(res.status_code, 400)
        self.assertIn("provider", res.data)
        self.assertFalse(Booking.objects.exists())

    def test_offers_are_limited_and_go_to_the_best_matches(self):
        online = [self.provider(f"+91984000000{i}", f"Online{i}", "600", online=True) for i in range(2)]
        for i in range(5):
            self.provider(f"+91985000000{i}", f"Extra{i}", str(300 + i))
        res = self.book()
        self.assertEqual(res.data["pending_offers"], MAX_OFFERS)
        offered = set(Booking.objects.get().requests.values_list("provider_id", flat=True))
        self.assertTrue({self.anita.pk, *[p.pk for p in online]} <= offered)   # online providers come first

    def test_providers_not_suitable_are_not_asked(self):
        self.provider("+919830000003", "NoSchedule", "300", window=False)
        self.provider("+919830000004", "Pending", "300", approved=False)
        res = self.book()
        self.assertEqual(res.data["pending_offers"], 2)

    def test_status_history_records_the_creation(self):
        self.book()
        log = BookingStatusLog.objects.get()
        self.assertEqual((log.to_status, log.changed_by), ("requested", self.customer))

    def test_no_provider_available_creates_nothing(self):
        res = self.book(scheduled_at=at(3, 10).isoformat())          # nobody has a schedule that day
        self.assertEqual(res.status_code, 400)
        self.assertIn("scheduled_at", res.data)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(BookingRequest.objects.exists())

    def test_time_rules(self):
        soon = (timezone.now() + timedelta(minutes=30)).isoformat()
        far = (timezone.now() + timedelta(days=120)).isoformat()
        past = at(-1, 10).isoformat()
        for label, value in {"soon": soon, "far": far, "past": past, "garbage": "tomorrow"}.items():
            res = self.book(scheduled_at=value)
            self.assertEqual(res.status_code, 400, label)
            self.assertIn("scheduled_at", res.data, label)

    def test_field_validation(self):
        other = make_user(User.Role.CUSTOMER, "+919820000002")
        theirs = CustomerAddress.objects.create(user=other, area=self.area, address_line="Someone else's address")
        gone = CustomerAddress.objects.create(user=self.customer, area=self.area, address_line="Archived address", is_active=False)
        inactive_service = Service.objects.create(category=self.service.category, name="Retired", base_price=1, is_active=False)
        cases = {
            "someone else's address": {"address": theirs.pk},
            "archived address": {"address": gone.pk},
            "unknown address": {"address": 99999},
            "unknown service": {"service": 99999},
            "inactive service": {"service": inactive_service.pk},
            "zero items": {"item_count": 0},
            "too many items": {"item_count": 51},
            "bad payment mode": {"payment_mode": "bitcoin"},
            "unknown provider": {"provider": 99999},
            "overlong notes": {"notes": "x" * 1001},
        }
        for label, extra in cases.items():
            self.assertEqual(self.book(**extra).status_code, 400, label)
        self.assertFalse(Booking.objects.exists())

    def test_service_not_offered_in_the_city_is_refused(self):
        lonely = Service.objects.create(category=self.service.category, name="Nobody offers this", base_price=100)
        res = self.book(service=lonely.pk)
        self.assertEqual(res.status_code, 400)
        self.assertIn("not available in your city", str(res.data["service"]))

    def test_access_rules(self):
        self.assertEqual(APIClient().post(reverse("booking-list"), self.body(), format="json").status_code, 401)
        for user in (self.anita.user, self.admin):
            self.as_user(user)
            self.assertEqual(self.book().status_code, 403)
        self.as_user(make_user(User.Role.CUSTOMER, "+919820000003", verified=False))
        res = self.book()
        self.assertEqual(res.status_code, 403)                          # needs a verified phone
        self.assertIn("Verify your phone", str(res.data))

    def test_database_rules(self):
        base = dict(
            customer=self.customer, service=self.service, address=self.address, area=self.area,
            scheduled_at=at(2, 10), duration_minutes=60, ends_at=at(2, 11), payment_mode="cash",
            service_name="x", pricing_type="fixed", unit_price=1, estimated_total=1,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(**{**base, "status": "accepted"})      # accepted needs a provider
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(**{**base, "ends_at": at(2, 9)})       # must end after it starts
        Booking.objects.create(**base)                                     # requested without provider is fine


class CustomerViewTests(BookingTestCase):
    def test_list_detail_filter_and_privacy(self):
        mine = self.book().data["id"]
        other = make_user(User.Role.CUSTOMER, "+919820000002")
        other_address = CustomerAddress.objects.create(user=other, area=self.area, address_line="Other person's flat")
        self.as_user(other)
        theirs = self.client.post(reverse("booking-list"), self.body(address=other_address.pk), format="json").data["id"]

        self.as_user(self.customer)
        res = self.client.get(reverse("booking-list"))
        self.assertEqual([b["id"] for b in res.data["results"]], [mine])
        self.assertNotIn("status_history", res.data["results"][0])
        self.assertEqual(self.client.get(reverse("booking-detail", args=[theirs])).status_code, 404)
        self.assertEqual(len(self.client.get(reverse("booking-detail", args=[mine])).data["status_history"]), 1)

        self.assertEqual(self.client.get(reverse("booking-list"), {"status": "requested"}).data["count"], 1)
        self.assertEqual(self.client.get(reverse("booking-list"), {"status": "cancelled"}).data["count"], 0)
        self.assertEqual(self.client.get(reverse("booking-list"), {"status": "nonsense"}).status_code, 400)

    def test_only_customers_can_list(self):
        for user in (self.anita.user, self.admin):
            self.as_user(user)
            self.assertEqual(self.client.get(reverse("booking-list")).status_code, 403)
        self.assertEqual(APIClient().get(reverse("booking-list")).status_code, 401)


class ProviderFlowTests(BookingTestCase):
    def test_provider_sees_the_offer_without_private_details(self):
        self.book(item_count=2, notes="Bring a ladder")
        self.as_user(self.anita.user)
        res = self.client.get(reverse("provider-request-list"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        b = res.data[0]["booking"]
        self.assertEqual(
            (b["service"], b["item_count"], b["notes"], b["unit_price"], b["estimated_total"], b["area"], b["pincode"], b["city"]),
            ("Tap repair", 2, "Bring a ladder", "500.00", "1000.00", "Indiranagar", "560038", "Bengaluru"),
        )
        shown = str(res.data)
        for secret in ("12 Test Street", "Near the park", "+919820000001", "Test User", "latitude"):
            self.assertNotIn(secret, shown)

    def test_expired_and_foreign_offers_are_not_listed(self):
        self.book()
        BookingRequest.objects.filter(provider=self.anita).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.as_user(self.anita.user)
        self.assertEqual(self.client.get(reverse("provider-request-list")).data, [])
        self.as_user(self.bala.user)
        self.assertEqual(len(self.client.get(reverse("provider-request-list")).data), 1)

    def test_accepting_assigns_the_booking_and_withdraws_the_other_offers(self):
        booking_id = self.book().data["id"]
        res = self.accept(self.anita, self.offer_for(self.anita))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "accepted")
        self.assertEqual(res.data["address"]["address_line"], "12 Test Street, Block A")     # now visible
        self.assertEqual(res.data["customer"], {"name": "Test User", "phone": "+919820000001"})

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual((booking.assigned_provider, booking.status), (self.anita, "accepted"))
        self.assertIsNotNone(booking.accepted_at)
        self.assertEqual(self.offer_for(self.anita).status, "accepted")
        self.assertEqual(self.offer_for(self.bala).status, "withdrawn")
        self.assertEqual(list(booking.status_logs.values_list("to_status", flat=True)), ["requested", "accepted"])

        self.as_user(self.customer)                                           # the customer now sees who is coming
        detail = self.client.get(reverse("booking-detail", args=[booking_id])).data
        self.assertEqual(detail["provider"], {"id": self.anita.pk, "display_name": "Anita", "phone": "+919830000001"})
        self.assertEqual(detail["pending_offers"], 0)

    def test_accepting_uses_the_providers_own_duration(self):
        slow = self.provider("+919830000003", "Slow", "450", minutes=90)
        booking_id = self.book(provider=slow.pk).data["id"]
        self.accept(slow, self.offer_for(slow))
        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.duration_minutes, 90)
        self.assertEqual(booking.ends_at, booking.scheduled_at + timedelta(minutes=90))

    def test_the_second_provider_to_accept_loses(self):
        booking_id = self.book().data["id"]
        self.accept(self.anita, self.offer_for(self.anita))
        res = self.accept(self.bala, self.offer_for(self.bala))
        self.assertEqual(res.status_code, 409)
        self.assertIn("already taken", str(res.data))
        self.assertEqual(Booking.objects.get(pk=booking_id).assigned_provider, self.anita)
        self.assertEqual(self.decline(self.bala, self.offer_for(self.bala)).status_code, 409)   # declining is no use either

    def test_cannot_accept_twice_or_someone_elses_offer(self):
        self.book()
        offer_a = self.offer_for(self.anita)
        self.accept(self.anita, offer_a)
        again = self.accept(self.anita, offer_a)
        self.assertEqual(again.status_code, 400)
        self.assertIn("already accepted", str(again.data))
        self.as_user(self.bala.user)
        self.assertEqual(self.client.post(reverse("provider-request-accept", args=[offer_a.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("provider-request-accept", args=[99999])).status_code, 404)

    def test_expired_offers_cannot_be_accepted_and_the_booking_expires(self):
        booking_id = self.book().data["id"]
        BookingRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        res = self.accept(self.anita, self.offer_for(self.anita))
        self.assertEqual(res.status_code, 400)
        self.assertIn("expired", str(res.data))
        self.assertEqual(self.offer_for(self.anita).status, "expired")                # persisted, not rolled back
        self.assertEqual(Booking.objects.get(pk=booking_id).status, "expired")
        self.assertEqual(Booking.objects.get(pk=booking_id).assigned_provider, None)

    def test_provider_whose_account_is_no_longer_approved_cannot_accept(self):
        self.book()
        ProviderProfile.objects.filter(pk=self.anita.pk).update(approval_status=Status.SUSPENDED)
        res = self.accept(self.anita, self.offer_for(self.anita))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(Booking.objects.get().status, "requested")

    def test_provider_who_changed_their_schedule_cannot_accept(self):
        self.book()
        ProviderAvailability.objects.filter(provider=self.anita).delete()
        res = self.accept(self.anita, self.offer_for(self.anita))
        self.assertEqual(res.status_code, 400)
        self.assertIn("not available", str(res.data))
        self.assertEqual(self.offer_for(self.anita).status, "offered")                 # still open

    def test_double_booking_is_prevented(self):
        first = self.book().data["id"]
        second = self.book(scheduled_at=at(2, 10, 30).isoformat()).data["id"]          # overlaps the first
        self.accept(self.anita, self.offer_for(self.anita, first))
        res = self.accept(self.anita, self.offer_for(self.anita, second))
        self.assertEqual(res.status_code, 400)
        self.assertIn("overlaps", str(res.data))
        self.assertEqual(self.accept(self.bala, self.offer_for(self.bala, second)).status_code, 200)   # Bala is free

    def test_back_to_back_bookings_are_allowed(self):
        first = self.book().data["id"]                                                  # 10:00 - 11:00
        second = self.book(scheduled_at=at(2, 11).isoformat()).data["id"]               # 11:00 - 12:00
        self.accept(self.anita, self.offer_for(self.anita, first))
        self.assertEqual(self.accept(self.anita, self.offer_for(self.anita, second)).status_code, 200)

    def test_busy_providers_are_not_offered_new_bookings_or_listed_for_that_time(self):
        first = self.book().data["id"]
        self.accept(self.anita, self.offer_for(self.anita, first))

        self.as_user(self.customer)
        res = self.book(scheduled_at=at(2, 10, 30).isoformat())
        self.assertEqual(res.data["pending_offers"], 1)                                 # only Bala
        self.assertFalse(BookingRequest.objects.filter(booking_id=res.data["id"], provider=self.anita).exists())

        url = reverse("service-provider-list", args=[self.service.pk])
        listed = lambda t: sorted(r["display_name"] for r in self.client.get(url, {"scheduled_at": t.isoformat()}).data["results"])
        self.assertEqual(listed(at(2, 10, 30)), ["Bala"])
        self.assertEqual(listed(at(2, 11)), ["Anita", "Bala"])                          # Anita is free again at 11:00

        only_anita = self.book(provider=self.anita.pk, scheduled_at=at(2, 10, 15).isoformat())
        self.assertEqual(only_anita.status_code, 400)                                   # and cannot be chosen directly

    def test_decline_keeps_the_booking_open_until_everyone_has_answered(self):
        booking_id = self.book().data["id"]
        res = self.decline(self.anita, self.offer_for(self.anita), reason="Too far away")
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["status"],), ("declined",))
        self.assertEqual(self.offer_for(self.anita).decline_reason, "Too far away")
        self.assertEqual(Booking.objects.get(pk=booking_id).status, "requested")        # Bala can still accept
        self.assertEqual(self.accept(self.bala, self.offer_for(self.bala)).status_code, 200)

    def test_when_every_provider_declines_the_booking_expires(self):
        booking_id = self.book().data["id"]
        self.decline(self.anita, self.offer_for(self.anita))
        self.decline(self.bala, self.offer_for(self.bala))
        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.status, "expired")
        self.assertEqual(list(booking.status_logs.values_list("to_status", flat=True)), ["requested", "expired"])
        self.as_user(self.customer)
        self.assertEqual(self.client.get(reverse("booking-detail", args=[booking_id])).data["status"], "expired")

    def test_cannot_decline_twice_or_after_accepting(self):
        self.book()
        offer_a, offer_b = self.offer_for(self.anita), self.offer_for(self.bala)
        self.assertEqual(self.decline(self.anita, offer_a).status_code, 200)
        self.assertEqual(self.decline(self.anita, offer_a).status_code, 400)
        self.assertEqual(self.accept(self.bala, offer_b).status_code, 200)
        self.assertEqual(self.decline(self.bala, offer_b).status_code, 400)      # already accepted by you

    def test_provider_booking_list_and_detail(self):
        mine = self.book().data["id"]
        self.accept(self.anita, self.offer_for(self.anita))
        self.as_user(self.anita.user)
        res = self.client.get(reverse("provider-booking-list"))
        self.assertEqual([b["id"] for b in res.data["results"]], [mine])
        self.assertEqual(self.client.get(reverse("provider-booking-list"), {"status": "completed"}).data["count"], 0)
        self.assertEqual(self.client.get(reverse("provider-booking-detail", args=[mine])).status_code, 200)
        self.as_user(self.bala.user)                                                      # Bala was not assigned
        self.assertEqual(self.client.get(reverse("provider-booking-detail", args=[mine])).status_code, 404)
        self.assertEqual(self.client.get(reverse("provider-booking-list")).data["count"], 0)

    def test_provider_endpoints_need_the_provider_role(self):
        self.book()
        offer_a = self.offer_for(self.anita)
        urls = [reverse("provider-request-list"), reverse("provider-booking-list")]
        for user in (self.customer, self.admin):
            self.as_user(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(reverse("provider-request-accept", args=[offer_a.pk])).status_code, 403)
        self.assertEqual(APIClient().get(urls[0]).status_code, 401)


class ExpiryTests(BookingTestCase):
    def test_expire_command_and_lazy_expiry(self):
        booking_id = self.book().data["id"]
        BookingRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        # customer polling the booking is enough to expire it (no cron needed in development)
        self.assertEqual(self.client.get(reverse("booking-detail", args=[booking_id])).data["status"], "expired")
        self.assertEqual(BookingRequest.objects.filter(status="expired").count(), 2)

    def test_management_command(self):
        import io

        self.book()
        BookingRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        out = io.StringIO()
        call_command("expire_booking_requests", stdout=out)
        self.assertIn("Expired 2 offer(s)", out.getvalue())
        self.assertEqual(Booking.objects.get().status, "expired")
        call_command("expire_booking_requests", stdout=out)                               # idempotent

    def test_fresh_offers_are_left_alone(self):
        self.book()
        from .services import expire_stale_requests

        self.assertEqual(expire_stale_requests(), 0)
        self.assertEqual(Booking.objects.get().status, "requested")

    def test_an_accepted_booking_is_never_expired(self):
        self.book()
        self.accept(self.anita, self.offer_for(self.anita))
        BookingRequest.objects.update(expires_at=timezone.now() - timedelta(days=1))
        from .services import expire_stale_requests

        expire_stale_requests()
        self.assertEqual(Booking.objects.get().status, "accepted")


class AdminViewTests(BookingTestCase):
    def test_admin_can_list_and_inspect_every_booking(self):
        booking_id = self.book().data["id"]
        self.accept(self.anita, self.offer_for(self.anita))
        self.as_user(self.admin)
        res = self.client.get(reverse("admin-booking-list"))
        self.assertEqual(res.data["count"], 1)
        row = res.data["results"][0]
        self.assertEqual((row["customer"]["phone"], row["status"]), ("+919820000001", "accepted"))
        self.assertEqual(len(row["offers"]), 2)
        self.assertEqual(self.client.get(reverse("admin-booking-list"), {"search": "JB000"}).data["count"], 1)
        self.assertEqual(self.client.get(reverse("admin-booking-list"), {"status": "requested"}).data["count"], 0)
        detail = self.client.get(reverse("admin-booking-detail", args=[booking_id]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.data["status_history"]), 2)
        self.assertEqual(self.client.get(reverse("admin-booking-detail", args=[99999])).status_code, 404)

    def test_only_admins(self):
        self.book()
        for user in (self.customer, self.anita.user):
            self.as_user(user)
            self.assertEqual(self.client.get(reverse("admin-booking-list")).status_code, 403)
        self.assertEqual(APIClient().get(reverse("admin-booking-list")).status_code, 401)