import calendar
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.locations.models import Area, City
from apps.providers.models import ProviderAvailability

from .models import Booking
from .tests import BookingTestCase, at, day
from .services import MIN_LEAD

User = get_user_model()


class AvailabilityTestCase(BookingTestCase):
    """Anita and Bala both work 09:00-17:00 on day(2); the service takes 60 minutes."""

    def slots(self, d=None, **params):
        params = {"service": self.service.pk, "city": self.city.pk, "date": (d or day(2)).isoformat(), **params}
        return self.client.get(reverse("booking-slots"), params)

    def calendar(self, month=None, **params):
        d = day(2)
        params = {"service": self.service.pk, "city": self.city.pk, "month": month or f"{d:%Y-%m}", **params}
        return self.client.get(reverse("booking-availability"), params)

    def busy(self, provider, hour, minutes=60):
        return self.direct_booking(provider, at(2, hour), minutes)

    def direct_booking(self, provider, start, minutes):
        return Booking.objects.create(
            customer=self.customer, service=self.service, address=self.address, area=self.area,
            scheduled_at=start, duration_minutes=minutes, ends_at=start + timedelta(minutes=minutes), payment_mode="cash",
            service_name="Tap repair", pricing_type="fixed", unit_price=500, estimated_total=500,
            status="accepted", assigned_provider=provider, start_code="123456",
        )


class SlotsTests(AvailabilityTestCase):
    def test_free_start_times_of_a_day(self):
        res = self.slots()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["price"], res.data["currency"], res.data["duration_minutes"]), ("500.00", "INR", 60))
        slots = res.data["slots"]
        self.assertEqual([s["start"] for s in slots], [f"{h:02d}:00" for h in range(9, 17)])      # 09:00 .. 16:00
        self.assertEqual(slots[0], {"start": "09:00", "end": "10:00", "start_at": at(2, 9).isoformat(), "providers": 2})
        self.assertTrue(all(s["providers"] == 2 for s in slots))

    def test_booked_providers_drop_out_of_the_slots_they_occupy(self):
        self.busy(self.anita, 10)                                          # Anita 10:00-11:00
        counts = {s["start"]: s["providers"] for s in self.slots().data["slots"]}
        self.assertEqual((counts["09:00"], counts["10:00"], counts["11:00"]), (2, 1, 2))          # back to back is fine
        self.busy(self.bala, 10)
        starts = [s["start"] for s in self.slots().data["slots"]]
        self.assertNotIn("10:00", starts)                                  # nobody left at 10:00
        self.assertEqual(len(starts), 7)

    def test_long_jobs_block_the_slots_they_overlap(self):
        self.busy(self.anita, 12, minutes=150)                             # Anita 12:00-14:30
        counts = {s["start"]: s["providers"] for s in self.slots().data["slots"]}
        self.assertEqual([counts[h] for h in ("11:00", "12:00", "13:00", "14:00", "15:00")], [2, 1, 1, 1, 2])

    def test_a_provider_whose_window_is_too_short_is_not_counted(self):
        ProviderAvailability.objects.filter(provider=self.bala).update(end_time="12:30")
        counts = {s["start"]: s["providers"] for s in self.slots().data["slots"]}
        self.assertEqual((counts["11:00"], counts["12:00"]), (2, 1))       # a 12:00 job would end at 13:00

    def test_blocked_time_removes_slots(self):
        ProviderAvailability.objects.create(provider=self.anita, available_date=day(2), start_time="13:00", end_time="14:00", is_available=False)
        counts = {s["start"]: s["providers"] for s in self.slots().data["slots"]}
        self.assertEqual((counts["12:00"], counts["13:00"], counts["14:00"]), (2, 1, 2))

    def test_times_that_are_too_soon_are_not_offered(self):
        ProviderAvailability.objects.create(provider=self.anita, available_date=day(0), start_time="00:00", end_time="23:59")
        cutoff = timezone.now() + MIN_LEAD
        for slot in self.slots(day(0)).data["slots"]:
            self.assertGreaterEqual(timezone.datetime.fromisoformat(slot["start_at"]), cutoff)

    def test_day_without_schedules_has_no_slots(self):
        self.assertEqual(self.slots(day(3)).data["slots"], [])

    def test_the_area_filter_uses_who_covers_that_area(self):
        other = Area.objects.create(city=self.city, name="Koramangala", pincode="560034")
        self.assertEqual(len(self.slots(area=self.area.pk, city="").data["slots"]), 8)
        self.assertEqual(self.slots(area=other.pk, city="").data["slots"], [])

    def test_validation(self):
        other_city = City.objects.create(name="Chennai", state="Tamil Nadu")
        other_city_area = Area.objects.create(city=other_city, name="Adyar", pincode="600020")
        inactive = Area.objects.create(city=self.city, name="Old", pincode="560001", is_active=False)
        url, base = reverse("booking-slots"), {"service": self.service.pk, "city": self.city.pk, "date": day(2).isoformat()}
        bad = [
            {"date": "tomorrow"}, {"date": ""}, {"date": (day(-1)).isoformat()}, {"date": day(91).isoformat()},
            {"city": "abc"}, {"city": 99999}, {"area": "abc"}, {"area": 99999}, {"area": inactive.pk},
            {"area": other_city_area.pk},                                  # in another city than ?city=
            {"city": "", "area": ""},                                      # neither
        ]
        for override in bad:
            params = {k: v for k, v in {**base, **override}.items() if v != ""}
            self.assertEqual(self.client.get(url, params).status_code, 400, override)
        self.assertEqual(self.client.get(url, {k: v for k, v in base.items() if k != "service"}).status_code, 400)
        self.assertEqual(self.client.get(url, {**base, "service": 99999}).status_code, 404)
        self.service.is_active = False
        self.service.save()
        self.assertEqual(self.client.get(url, base).status_code, 404)

    def test_it_is_public_and_ignores_stale_tokens(self):
        self.client = type(self.client)()
        self.assertEqual(self.slots().status_code, 200)
        self.assertEqual(self.client.get(reverse("booking-slots"), {"service": self.service.pk, "city": self.city.pk, "date": day(2).isoformat()},
                                         HTTP_AUTHORIZATION="Bearer expired.garbage.token").status_code, 200)

    def test_it_never_names_a_provider(self):
        shown = str(self.slots().data) + str(self.calendar().data)
        for secret in ("Anita", "Bala", "+919830000001", "anita@example.com"):
            self.assertNotIn(secret, shown)


class CalendarTests(AvailabilityTestCase):
    def test_one_entry_per_day_with_a_status_and_price(self):
        d = day(2)
        res = self.calendar()
        self.assertEqual(res.status_code, 200, res.data)
        days = res.data["days"]
        self.assertEqual(res.data["month"], f"{d:%Y-%m}")
        self.assertEqual(len(days), calendar.monthrange(d.year, d.month)[1])
        by_date = {x["date"]: x for x in days}
        self.assertEqual(by_date[d.isoformat()], {"date": d.isoformat(), "status": "available", "slots": 8, "price": "500.00"})
        today = timezone.localdate()
        if today.day > 1:
            self.assertEqual(by_date[today.replace(day=1).isoformat()]["status"], "past")
            self.assertIsNone(by_date[today.replace(day=1).isoformat()]["price"])

    def test_days_without_providers_are_unavailable(self):
        d = day(3)
        entry = {x["date"]: x for x in self.calendar(f"{d:%Y-%m}").data["days"]}[d.isoformat()]
        self.assertEqual((entry["status"], entry["slots"], entry["price"]), ("unavailable", 0, None))

    def test_a_day_with_only_a_few_free_start_times_is_limited(self):
        ProviderAvailability.objects.filter(available_date=day(2)).delete()
        ProviderAvailability.objects.create(provider=self.anita, available_date=day(2), start_time="09:00", end_time="12:00")
        d = day(2)
        entry = {x["date"]: x for x in self.calendar().data["days"]}[d.isoformat()]
        self.assertEqual((entry["status"], entry["slots"], entry["price"]), ("limited", 3, "500.00"))      # 09, 10, 11

    def test_a_fully_booked_day_becomes_unavailable(self):
        for provider in (self.anita, self.bala):
            self.direct_booking(provider, at(2, 9), 8 * 60)               # 09:00-17:00
        d = day(2)
        entry = {x["date"]: x for x in self.calendar().data["days"]}[d.isoformat()]
        self.assertEqual((entry["status"], entry["slots"]), ("unavailable", 0))

    def test_days_beyond_the_booking_horizon_are_unavailable(self):
        far = timezone.localdate() + timedelta(days=100)
        res = self.client.get(reverse("booking-availability"), {"service": self.service.pk, "city": self.city.pk, "month": f"{far:%Y-%m}"})
        self.assertEqual(res.status_code, 400)                            # that month is not offered at all

    def test_default_month_is_the_current_one(self):
        res = self.client.get(reverse("booking-availability"), {"service": self.service.pk, "city": self.city.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["month"], f"{timezone.localdate():%Y-%m}")

    def test_validation(self):
        url, base = reverse("booking-availability"), {"service": self.service.pk, "city": self.city.pk}
        last_month = (timezone.localdate().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        for month in ("2026-13", "2026-1", "november", "", "0000-00", last_month):
            params = {**base, **({"month": month} if month else {})}
            if month == "":
                self.assertEqual(self.client.get(url, params).status_code, 200)        # empty = default
            else:
                self.assertEqual(self.client.get(url, params).status_code, 400, month)
        self.assertEqual(self.client.get(url, {"service": self.service.pk}).status_code, 400)       # no location
        self.assertEqual(self.client.get(url, {**base, "service": 99999}).status_code, 404)

    def test_the_number_of_queries_does_not_grow_with_providers(self):
        def queries():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.calendar().status_code, 200)
                self.assertEqual(self.slots().status_code, 200)
            return len(ctx)

        few = queries()
        for i in range(8):
            self.provider(f"+91986000000{i}", f"Extra{i}", "300")
        self.assertEqual(queries(), few)
        self.assertLessEqual(few, 12)
