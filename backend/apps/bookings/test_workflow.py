from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Booking, BookingRequest
from .services import FREE_CANCEL_WINDOW, MAX_START_ATTEMPTS
from .tests import BookingTestCase, Status, User, at, day, make_user


class WorkflowTestCase(BookingTestCase):
    def direct(self, *, status="accepted", provider="anita", scheduled_at=None, minutes=60, code="123456", **extra):
        """Create a booking straight in the database, in any state and at any time."""
        scheduled_at = scheduled_at or at(2, 10)
        provider = {"anita": self.anita, "bala": self.bala, None: None}[provider] if isinstance(provider, (str, type(None))) else provider
        fields = dict(
            customer=self.customer, service=self.service, address=self.address, area=self.area,
            scheduled_at=scheduled_at, duration_minutes=minutes, ends_at=scheduled_at + timedelta(minutes=minutes),
            payment_mode="cash", service_name="Tap repair", pricing_type="fixed", unit_price=500, estimated_total=500,
            address_snapshot={"address_line": "12 Test Street, Block A", "area": "Indiranagar", "pincode": "560038", "city": "Bengaluru"},
            status=status, assigned_provider=provider,
        )
        if status in ("accepted", "in_progress", "completed"):
            fields["start_code"] = code
        if status in ("in_progress", "completed"):
            fields["started_at"] = scheduled_at
        if status == "completed":
            fields["completed_at"] = scheduled_at + timedelta(minutes=minutes)
        if status == "cancelled":
            fields.update(cancelled_at=timezone.now(), cancellation_reason_code="changed_mind", cancelled_by_role="customer")
        fields.update(extra)
        return Booking.objects.create(**fields)

    def customer_cancel(self, booking, reason_code="changed_mind", note=""):
        self.as_user(self.customer)
        return self.client.post(reverse("booking-cancel", args=[booking.pk]), {"reason_code": reason_code, "note": note}, format="json")

    def provider_cancel(self, provider, booking, reason_code="provider_unavailable", note=""):
        self.as_user(provider.user)
        return self.client.post(reverse("provider-booking-cancel", args=[booking.pk]), {"reason_code": reason_code, "note": note}, format="json")

    def admin_cancel(self, booking, reason_code="policy_violation", note=""):
        self.as_user(self.admin)
        return self.client.post(reverse("admin-booking-cancel", args=[booking.pk]), {"reason_code": reason_code, "note": note}, format="json")

    def start(self, provider, booking, code="123456"):
        self.as_user(provider.user)
        return self.client.post(reverse("provider-booking-start", args=[booking.pk]), {"code": code}, format="json")

    def complete(self, provider, booking, **body):
        self.as_user(provider.user)
        return self.client.post(reverse("provider-booking-complete", args=[booking.pk]), body, format="json")


class CustomerCancellationTests(WorkflowTestCase):
    def test_cancelling_a_requested_booking_withdraws_the_offers(self):
        booking_id = self.book().data["id"]
        res = self.customer_cancel(Booking.objects.get(pk=booking_id), "found_another_provider", "Neighbour recommended someone")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "cancelled")
        cancellation = res.data["cancellation"]
        self.assertEqual(
            (cancellation["by"], cancellation["reason_code"], cancellation["reason"], cancellation["note"], cancellation["late"]),
            ("customer", "found_another_provider", "I found another provider", "Neighbour recommended someone", False),
        )
        self.assertFalse(res.data["can_cancel"])
        self.assertEqual(set(BookingRequest.objects.values_list("status", flat=True)), {"withdrawn"})
        self.as_user(self.anita.user)
        self.assertEqual(self.client.get(reverse("provider-request-list")).data, [])      # nothing left to answer
        log = Booking.objects.get(pk=booking_id).status_logs.last()
        self.assertEqual((log.to_status, log.changed_by), ("cancelled", self.customer))
        self.assertIn("Cancelled by the customer", log.remarks)

    def test_cancelling_an_accepted_booking_is_free_when_there_is_time(self):
        booking = self.direct(scheduled_at=timezone.now() + timedelta(hours=5))
        res = self.customer_cancel(booking)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["cancellation"]["late"])
        self.assertFalse(Booking.objects.get(pk=booking.pk).cancelled_late)

    def test_cancelling_close_to_the_start_is_flagged_late(self):
        booking = self.direct(scheduled_at=timezone.now() + FREE_CANCEL_WINDOW - timedelta(minutes=15))
        res = self.customer_cancel(booking)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["cancellation"]["late"])
        self.assertIn("late cancellation", Booking.objects.get(pk=booking.pk).status_logs.last().remarks)

    def test_the_booking_tells_the_ui_until_when_cancelling_is_free(self):
        booking = self.direct(scheduled_at=timezone.now() + timedelta(hours=5))
        self.as_user(self.customer)
        data = self.client.get(reverse("booking-detail", args=[booking.pk])).data
        self.assertTrue(data["can_cancel"])
        self.assertEqual(data["free_cancellation_until"], booking.scheduled_at - FREE_CANCEL_WINDOW)   # the same instant
        requested = self.direct(status="requested", provider=None)
        self.assertIsNone(self.client.get(reverse("booking-detail", args=[requested.pk])).data["free_cancellation_until"])

    def test_reason_rules(self):
        booking = self.direct(status="requested", provider=None)
        self.assertEqual(self.customer_cancel(booking, "emergency").status_code, 400)             # a provider's reason
        self.assertEqual(self.customer_cancel(booking, "nonsense").status_code, 400)
        self.assertEqual(self.customer_cancel(booking, "other").status_code, 400)                  # 'other' needs a note
        self.assertEqual(self.customer_cancel(booking, "other", "   ").status_code, 400)
        self.assertEqual(self.customer_cancel(booking, "changed_mind", "x" * 501).status_code, 400)
        self.as_user(self.customer)
        self.assertEqual(self.client.post(reverse("booking-cancel", args=[booking.pk]), {}, format="json").status_code, 400)
        self.assertEqual(Booking.objects.get(pk=booking.pk).status, "requested")
        self.assertEqual(self.customer_cancel(booking, "other", "It rained").status_code, 200)

    def test_finished_or_started_bookings_cannot_be_cancelled_by_the_customer(self):
        for status in ("in_progress", "completed", "cancelled", "expired"):
            booking = self.direct(status=status, provider="anita" if status in ("in_progress", "completed") else None)
            res = self.customer_cancel(booking)
            self.assertEqual(res.status_code, 400, status)
            self.assertEqual(Booking.objects.get(pk=booking.pk).status, status)
        started = self.direct(status="in_progress")
        self.assertIn("contact support", str(self.customer_cancel(started).data))

    def test_someone_elses_booking_is_404_and_roles_are_enforced(self):
        booking = self.direct()
        other = make_user(User.Role.CUSTOMER, "+919820000002")
        self.as_user(other)
        url = reverse("booking-cancel", args=[booking.pk])
        self.assertEqual(self.client.post(url, {"reason_code": "changed_mind"}, format="json").status_code, 404)
        for user in (self.anita.user, self.admin):
            self.as_user(user)
            self.assertEqual(self.client.post(url, {"reason_code": "changed_mind"}, format="json").status_code, 403)
        self.assertEqual(APIClient().post(url, {"reason_code": "changed_mind"}, format="json").status_code, 401)

    def test_a_cancelled_booking_frees_the_providers_time(self):
        booking_id = self.book().data["id"]
        self.accept(self.anita, self.offer_for(self.anita))
        url = reverse("service-provider-list", args=[self.service.pk])
        names = lambda: sorted(r["display_name"] for r in self.client.get(url, {"scheduled_at": at(2, 10).isoformat()}).data["results"])
        self.assertEqual(names(), ["Bala"])
        self.assertEqual(self.customer_cancel(Booking.objects.get(pk=booking_id)).status_code, 200)
        self.assertEqual(names(), ["Anita", "Bala"])
        self.as_user(self.customer)
        self.assertEqual(self.book().data["pending_offers"], 2)


class ProviderAndAdminCancellationTests(WorkflowTestCase):
    def test_a_provider_can_withdraw_from_an_accepted_booking(self):
        booking = self.direct(scheduled_at=timezone.now() + timedelta(days=1))
        res = self.provider_cancel(self.anita, booking, "emergency", "Family emergency")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "cancelled")
        self.assertEqual((res.data["cancellation"]["by"], res.data["cancellation"]["reason_code"]), ("provider", "emergency"))
        self.assertFalse(res.data["cancellation"]["late"])
        booking.refresh_from_db()
        self.assertEqual((booking.cancelled_by, booking.cancelled_by_role), (self.anita.user, "provider"))
        self.as_user(self.customer)                                                  # the customer sees why
        self.assertEqual(self.client.get(reverse("booking-detail", args=[booking.pk])).data["cancellation"]["reason_code"], "emergency")

    def test_a_late_withdrawal_is_flagged(self):
        booking = self.direct(scheduled_at=timezone.now() + timedelta(minutes=90))
        self.assertTrue(self.provider_cancel(self.anita, booking).data["cancellation"]["late"])

    def test_provider_rules(self):
        booking = self.direct(scheduled_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.provider_cancel(self.anita, booking, "changed_mind").status_code, 400)      # a customer's reason
        self.assertEqual(self.provider_cancel(self.anita, booking, "other").status_code, 400)
        self.assertEqual(self.provider_cancel(self.bala, booking).status_code, 404)                        # not their booking
        self.assertEqual(Booking.objects.get(pk=booking.pk).status, "accepted")
        for status in ("in_progress", "completed"):
            self.assertEqual(self.provider_cancel(self.anita, self.direct(status=status)).status_code, 400, status)
        requested = self.direct(status="requested", provider=None)
        self.assertEqual(self.provider_cancel(self.anita, requested).status_code, 404)                     # decline offers instead
        for user in (self.customer, self.admin):
            self.as_user(user)
            self.assertEqual(self.client.post(reverse("provider-booking-cancel", args=[booking.pk]), {"reason_code": "emergency"}, format="json").status_code, 403)

    def test_admin_can_cancel_anything_not_finished(self):
        for status in ("requested", "accepted", "in_progress"):
            booking = self.direct(status=status, provider=None if status == "requested" else "anita")
            res = self.admin_cancel(booking, "policy_violation", "Support decision")
            self.assertEqual(res.status_code, 200, status)
            self.assertEqual((res.data["status"], res.data["cancellation"]["by"], res.data["cancellation"]["late"]), ("cancelled", "admin", False))
        for status in ("completed", "cancelled", "expired"):
            booking = self.direct(status=status, provider="anita" if status == "completed" else None)
            self.assertEqual(self.admin_cancel(booking).status_code, 400, status)
        for user in (self.customer, self.anita.user):
            self.as_user(user)
            self.assertEqual(self.client.post(reverse("admin-booking-cancel", args=[booking.pk]), {"reason_code": "other", "note": "x"}, format="json").status_code, 403)
        self.assertEqual(self.admin_cancel(self.direct(), "changed_mind").status_code, 200)     # admins may use any reason

    def test_cancel_reasons_endpoint(self):
        self.as_user(self.customer)
        data = self.client.get(reverse("booking-cancel-reasons")).data
        self.assertEqual({r["code"] for r in data["customer"]}, {"changed_mind", "booked_by_mistake", "found_another_provider", "schedule_conflict", "price_too_high", "other"})
        self.assertIn({"code": "emergency", "label": "An emergency came up"}, data["provider"])
        self.assertIn("policy_violation", {r["code"] for r in data["admin"]})
        self.assertEqual(APIClient().get(reverse("booking-cancel-reasons")).status_code, 401)


class StartAndCompleteTests(WorkflowTestCase):
    def soon(self, **extra):
        """An accepted booking whose start window is open right now."""
        return self.direct(scheduled_at=timezone.now() + timedelta(minutes=30), **extra)

    def test_the_customer_sees_the_code_and_the_provider_never_does(self):
        booking = self.soon()
        self.as_user(self.customer)
        self.assertEqual(self.client.get(reverse("booking-detail", args=[booking.pk])).data["start_code"], "123456")
        self.assertEqual(self.client.get(reverse("booking-list")).data["results"][0]["start_code"], "123456")
        self.as_user(self.anita.user)
        for url in (reverse("provider-booking-detail", args=[booking.pk]), reverse("provider-booking-list")):
            self.assertNotIn("123456", str(self.client.get(url).data))
        self.assertNotIn("start_code", self.client.get(reverse("provider-booking-detail", args=[booking.pk])).data)

    def test_accepting_creates_a_fresh_random_code(self):
        self.book()
        self.accept(self.anita, self.offer_for(self.anita))
        code = Booking.objects.get().start_code
        self.assertRegex(code, r"^\d{6}$")
        self.as_user(self.customer)
        self.assertEqual(self.client.get(reverse("booking-detail", args=[Booking.objects.get().pk])).data["start_code"], code)

    def test_starting_with_the_right_code(self):
        booking = self.soon()
        res = self.start(self.anita, booking)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "in_progress")
        self.assertIsNotNone(res.data["started_at"])
        self.assertFalse(res.data["can_start"])
        self.assertEqual(res.data["status_history"][-1]["to_status"], "in_progress")
        self.assertNotIn("123456", str(res.data))
        self.as_user(self.customer)                                                     # the code disappears once used
        detail = self.client.get(reverse("booking-detail", args=[booking.pk])).data
        self.assertEqual((detail["status"], detail["start_code"], detail["can_cancel"]), ("in_progress", None, False))

    def test_wrong_codes_are_counted_and_lock_the_job(self):
        booking = self.soon()
        res = self.start(self.anita, booking, "000000")
        self.assertEqual(res.status_code, 400)
        self.assertIn(f"{MAX_START_ATTEMPTS - 1} attempt(s) left", str(res.data))
        self.assertEqual(Booking.objects.get(pk=booking.pk).start_attempts, 1)             # committed, not rolled back
        for _ in range(MAX_START_ATTEMPTS - 1):
            self.start(self.anita, booking, "000000")
        locked = self.start(self.anita, booking, "123456")                                  # even the right code is refused now
        self.assertEqual(locked.status_code, 400)
        self.assertIn("contact support", str(locked.data))
        self.assertEqual(Booking.objects.get(pk=booking.pk).status, "accepted")
        self.as_user(self.admin)                                                            # support can see the code and the attempts
        admin_view = self.client.get(reverse("admin-booking-detail", args=[booking.pk])).data
        self.assertEqual((admin_view["start_code"], admin_view["start_attempts"]), ("123456", MAX_START_ATTEMPTS))

    def test_malformed_codes_are_not_counted(self):
        booking = self.soon()
        for bad in ("12345", "1234567", "abcdef", "", "12 456"):
            self.assertEqual(self.start(self.anita, booking, bad).status_code, 400, bad)
        self.assertEqual(Booking.objects.get(pk=booking.pk).start_attempts, 0)

    def test_start_window(self):
        early = self.direct(scheduled_at=timezone.now() + timedelta(hours=3))
        res = self.start(self.anita, early)
        self.assertEqual(res.status_code, 400)
        self.assertIn("You can start this job from", str(res.data))
        self.assertTrue(self.start(self.anita, self.direct(scheduled_at=timezone.now() + timedelta(minutes=50))).status_code == 200)
        stale = self.direct(scheduled_at=timezone.now() - timedelta(hours=7))
        self.assertIn("window has passed", str(self.start(self.anita, stale).data))
        late_but_ok = self.direct(scheduled_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(self.start(self.anita, late_but_ok).status_code, 200)

    def test_only_the_assigned_provider_can_start_an_accepted_booking(self):
        booking = self.soon()
        self.assertEqual(self.start(self.bala, booking).status_code, 404)
        for status in ("requested", "in_progress", "completed"):
            other = self.direct(status=status, provider=None if status == "requested" else "anita", scheduled_at=timezone.now() + timedelta(minutes=30))
            res = self.start(self.anita, other)
            self.assertIn(res.status_code, (400, 404), status)
            self.assertEqual(Booking.objects.get(pk=other.pk).status, status)
        for user in (self.customer, self.admin):
            self.as_user(user)
            self.assertEqual(self.client.post(reverse("provider-booking-start", args=[booking.pk]), {"code": "123456"}, format="json").status_code, 403)

    def test_a_booking_accepted_before_codes_existed_gets_one(self):
        booking = self.soon(code="")
        res = self.start(self.anita, booking)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Ask the customer", str(res.data))
        code = Booking.objects.get(pk=booking.pk).start_code
        self.assertRegex(code, r"^\d{6}$")                                      # created and kept
        self.assertEqual(self.start(self.anita, booking, code).status_code, 200)

    def test_completing_a_job(self):
        booking = self.soon()
        self.start(self.anita, booking)
        res = self.complete(self.anita, booking, note="Replaced the tap washer")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "completed")
        self.assertIsNotNone(res.data["completed_at"])
        booking.refresh_from_db()
        self.assertEqual(booking.status_logs.last().remarks, "Replaced the tap washer")
        self.assertEqual(self.complete(self.anita, booking).status_code, 400)         # not twice

    def test_only_a_started_job_by_its_provider_can_be_completed(self):
        accepted = self.soon()
        self.assertEqual(self.complete(self.anita, accepted).status_code, 400)        # must be started first
        started = self.direct(status="in_progress")
        self.assertEqual(self.complete(self.bala, started).status_code, 404)
        for user in (self.customer, self.admin):
            self.as_user(user)
            self.assertEqual(self.client.post(reverse("provider-booking-complete", args=[started.pk])).status_code, 403)
        self.assertEqual(Booking.objects.get(pk=started.pk).status, "in_progress")

    def test_the_whole_life_of_a_booking_is_in_the_history(self):
        booking_id = self.book().data["id"]
        self.accept(self.anita, self.offer_for(self.anita))
        booking = Booking.objects.get(pk=booking_id)
        Booking.objects.filter(pk=booking_id).update(scheduled_at=timezone.now() + timedelta(minutes=30), ends_at=timezone.now() + timedelta(minutes=90))
        self.start(self.anita, booking, booking.start_code)
        self.complete(self.anita, booking)
        self.as_user(self.customer)
        data = self.client.get(reverse("booking-detail", args=[booking_id])).data
        self.assertEqual([h["to_status"] for h in data["status_history"]], ["requested", "accepted", "in_progress", "completed"])
        self.assertEqual((data["status"], data["start_code"]), ("completed", None))
        self.assertIsNotNone(data["completed_at"])
        logs = list(Booking.objects.get(pk=booking_id).status_logs.all())
        self.assertEqual([l.changed_by for l in logs], [self.customer, self.anita.user, self.anita.user, self.anita.user])
        self.as_user(self.admin)
        self.assertEqual(len(self.client.get(reverse("admin-booking-detail", args=[booking_id])).data["status_history"]), 4)


class HistoryTests(WorkflowTestCase):
    def test_upcoming_and_history_scopes(self):
        a = self.direct(status="requested", provider=None, scheduled_at=at(5, 10))
        b = self.direct(status="accepted", scheduled_at=at(2, 10))
        c = self.direct(status="in_progress", scheduled_at=at(3, 10))
        d = self.direct(status="completed", scheduled_at=at(-3, 10))
        e = self.direct(status="cancelled", provider=None, scheduled_at=at(-1, 10))
        f = self.direct(status="expired", provider=None, scheduled_at=at(-2, 10))
        self.as_user(self.customer)
        ids = lambda **params: [r["id"] for r in self.client.get(reverse("booking-list"), params).data["results"]]
        self.assertEqual(ids(scope="upcoming"), [b.pk, c.pk, a.pk])                  # soonest first
        self.assertEqual(ids(scope="history"), [e.pk, f.pk, d.pk])                   # latest first
        self.assertEqual(ids(scope="upcoming", status="accepted"), [b.pk])           # combines with ?status=
        self.assertEqual(len(ids()), 6)
        self.assertEqual(self.client.get(reverse("booking-list"), {"scope": "later"}).status_code, 400)

    def test_providers_have_the_same_scopes(self):
        a = self.direct(status="accepted", scheduled_at=at(2, 10))
        b = self.direct(status="completed", scheduled_at=at(-3, 10))
        self.as_user(self.anita.user)
        ids = lambda **params: [r["id"] for r in self.client.get(reverse("provider-booking-list"), params).data["results"]]
        self.assertEqual(ids(scope="upcoming"), [a.pk])
        self.assertEqual(ids(scope="history"), [b.pk])
        self.assertEqual(self.client.get(reverse("provider-booking-list"), {"scope": "x"}).status_code, 400)

    def test_the_list_costs_a_fixed_number_of_queries(self):
        self.as_user(self.customer)

        def queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(reverse("booking-list"), {"scope": "upcoming"})
            return len(ctx)

        for i in range(3):
            self.direct(scheduled_at=at(2, 10 + i))
        few = queries()
        for i in range(10):
            self.direct(status="requested", provider=None, scheduled_at=at(4, 8 + i))
        self.assertEqual(queries(), few)                                           # no N+1


class DatabaseRuleTests(WorkflowTestCase):
    def test_the_database_enforces_the_life_cycle_fields(self):
        base = dict(
            customer=self.customer, service=self.service, address=self.address, area=self.area, scheduled_at=at(2, 10),
            duration_minutes=60, ends_at=at(2, 11), payment_mode="cash", service_name="x", pricing_type="fixed",
            unit_price=1, estimated_total=1,
        )
        bad = [
            {"status": "cancelled"},                                                     # no timestamp, no reason
            {"status": "cancelled", "cancelled_at": timezone.now()},                     # no reason
            {"status": "in_progress", "assigned_provider": self.anita},                  # never started
            {"status": "completed", "assigned_provider": self.anita, "started_at": timezone.now()},   # no completed_at
        ]
        for extra in bad:
            with self.assertRaises(IntegrityError), transaction.atomic():
                Booking.objects.create(**{**base, **extra})
        Booking.objects.create(**{**base, "status": "cancelled", "cancelled_at": timezone.now(), "cancellation_reason_code": "changed_mind"})
