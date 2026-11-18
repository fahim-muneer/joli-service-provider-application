from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.locations.models import Area, City
from apps.providers.factories import cover, make_provider, offer
from apps.providers.models import ProviderAvailability, ProviderProfile

from .models import Category, Service

User = get_user_model()


def day(n):
    return timezone.localdate() + timedelta(days=n)


def at(n, hour, minute=0):
    """An aware datetime n days from today at hour:minute, in the server's time zone."""
    return timezone.make_aware(datetime.combine(day(n), datetime.min.time()).replace(hour=hour, minute=minute))


class MatchingTests(APITestCase):
    def setUp(self):
        city = City.objects.create(name="Bengaluru", state="Karnataka")
        self.area = Area.objects.create(city=city, name="Indiranagar", pincode="560038")
        self.city = city
        self.service = Service.objects.create(
            category=Category.objects.create(name="Plumbing"), name="Tap repair", base_price=300,
            estimated_duration_minutes=60,
        )
        self.url = reverse("service-provider-list", args=[self.service.pk])

        # Anita: working 09-17 with lunch blocked 13-14, offer takes 60 min, cheaper
        self.anita = self.provider("+919800000001", "Anita", "250")
        self.window(self.anita, 2, "09:00", "17:00")
        self.window(self.anita, 2, "13:00", "14:00", blocked=True)
        # Bala: working 14-18 only, offer takes 120 min, pricier
        self.bala = self.provider("+919800000002", "Bala", "400", minutes=120)
        self.window(self.bala, 2, "14:00", "18:00")
        # Chitra: covers the area but has no schedule at all
        self.chitra = self.provider("+919800000003", "Chitra", "300")

    def provider(self, phone, name, price, minutes=None):
        profile = make_provider(phone, business_name=name)
        offer(profile, self.service, price=Decimal(price))
        if minutes:
            profile.provider_services.update(estimated_duration_minutes=minutes)
        cover(profile, self.area)
        return profile

    def window(self, profile, n, start, end, blocked=False):
        ProviderAvailability.objects.create(
            provider=profile, available_date=day(n), start_time=start, end_time=end, is_available=not blocked
        )

    def names(self, scheduled_at=None, **params):
        if scheduled_at is not None:
            params["scheduled_at"] = scheduled_at.isoformat() if hasattr(scheduled_at, "isoformat") else scheduled_at
        res = self.client.get(self.url, params)
        self.assertEqual(res.status_code, 200, res.data)
        return [r["display_name"] for r in res.data["results"]]

    def test_without_scheduled_at_everyone_is_listed(self):
        self.assertEqual(sorted(self.names()), ["Anita", "Bala", "Chitra"])

    def test_only_providers_free_at_that_time_are_returned(self):
        self.assertEqual(self.names(at(2, 10)), ["Anita"])                       # morning: Bala is not open yet
        self.assertEqual(sorted(self.names(at(2, 15))), ["Anita", "Bala"])        # afternoon: both are free

    def test_each_offers_own_duration_is_used(self):
        # 14:00 with 120 min ends 16:00 (fits Bala's 14-18); Anita's 60 min at 14:00 fits her 09-17 too
        self.assertEqual(sorted(self.names(at(2, 14))), ["Anita", "Bala"])
        # 16:30: Anita 60 min -> 17:30 runs past her 17:00 close; Bala 120 min -> 18:30 past her 18:00 close
        self.assertEqual(self.names(at(2, 16, 30)), [])
        # 16:00: Anita 60 min -> 17:00 fits exactly; Bala 120 min -> 18:00 fits exactly
        self.assertEqual(sorted(self.names(at(2, 16))), ["Anita", "Bala"])
        # 16:01 pushes Bala past 18:00 but Anita still ends 17:01 > 17:00 -> neither
        self.assertEqual(self.names(at(2, 16, 1)), [])

    def test_blocked_time_excludes_a_provider(self):
        self.assertEqual(self.names(at(2, 13)), [])                       # Anita's lunch; Bala not open yet
        self.assertEqual(self.names(at(2, 12, 30)), [])                   # 12:30-13:30 touches lunch
        self.assertEqual(self.names(at(2, 12)), ["Anita"])                # ends exactly as lunch starts

    def test_day_without_windows_and_providers_without_a_schedule_are_excluded(self):
        self.assertEqual(self.names(at(3, 10)), [])
        self.assertNotIn("Chitra", self.names(at(2, 10)))

    def test_ordering_is_preserved(self):
        self.assertEqual(self.names(at(2, 14)), ["Anita", "Bala"])                         # cheapest first
        self.assertEqual(self.names(at(2, 14), ordering="-price"), ["Bala", "Anita"])
        ProviderProfile.objects.filter(pk=self.bala.pk).update(is_available=True)          # online first
        self.assertEqual(self.names(at(2, 14)), ["Bala", "Anita"])

    def test_works_with_area_and_city_filters(self):
        other = Area.objects.create(city=self.city, name="Koramangala", pincode="560034")
        self.assertEqual(self.names(at(2, 10), area=self.area.pk), ["Anita"])
        self.assertEqual(self.names(at(2, 10), area=other.pk), [])
        self.assertEqual(self.names(at(2, 10), city=self.city.pk), ["Anita"])

    def test_unapproved_providers_never_match(self):
        ProviderProfile.objects.filter(pk=self.anita.pk).update(approval_status=ProviderProfile.ApprovalStatus.SUSPENDED)
        self.assertEqual(self.names(at(2, 10)), [])

    def test_time_zone_offsets_are_respected(self):
        ten_am_local = at(2, 10)
        utc = ten_am_local.astimezone(dt_timezone.utc)
        self.assertEqual(self.names(utc.isoformat()), ["Anita"])           # same instant written in UTC
        self.assertEqual(self.names(ten_am_local.replace(tzinfo=None).isoformat()), ["Anita"])   # naive = server zone

    def test_bad_scheduled_at_is_a_400(self):
        yesterday = at(-1, 10).isoformat()
        for bad in ("tomorrow", "2026-13-45T10:00:00", "10:00", yesterday):
            res = self.client.get(self.url, {"scheduled_at": bad})
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn("scheduled_at", res.data)

    def test_matching_uses_a_constant_number_of_queries(self):
        for i in range(6):
            extra = self.provider(f"+91980000010{i}", f"Extra {i}", "260")
            self.window(extra, 2, "09:00", "17:00")
        with self.assertNumQueries(5):          # service check + count + offers + windows + page of rows
            res = self.client.get(self.url, {"scheduled_at": at(2, 10).isoformat()})
        self.assertEqual(res.data["count"], 7)
