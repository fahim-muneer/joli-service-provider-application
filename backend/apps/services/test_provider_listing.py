from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Area, City
from apps.providers.factories import cover, make_provider, offer
from apps.providers.models import ProviderProfile

from .models import Category, Service

User = get_user_model()
Status = ProviderProfile.ApprovalStatus


class ProviderListingTests(APITestCase):
    def setUp(self):
        self.blr = City.objects.create(name="Bengaluru", state="Karnataka")
        self.che = City.objects.create(name="Chennai", state="Tamil Nadu")
        self.indira = Area.objects.create(city=self.blr, name="Indiranagar", pincode="560038")
        self.koram = Area.objects.create(city=self.blr, name="Koramangala", pincode="560034")
        self.adyar = Area.objects.create(city=self.che, name="Adyar", pincode="600020")
        self.category = Category.objects.create(name="Plumbing")
        self.tap = Service.objects.create(category=self.category, name="Tap repair", base_price=300)
        self.other_service = Service.objects.create(category=self.category, name="Pipe fix", base_price=500)

        # cheap, offline, 2 years, covers Indiranagar
        self.cheap = make_provider("+919600000001", business_name="Cheap Plumbers", email="cheap@example.com")
        offer(self.cheap, self.tap, price=Decimal("250"))
        cover(self.cheap, self.indira)
        ProviderProfile.objects.filter(pk=self.cheap.pk).update(experience_years=2, is_available=False)
        # pricier, ONLINE, 9 years, covers Koramangala
        self.pro = make_provider("+919600000002", business_name="Pro Plumbers")
        offer(self.pro, self.tap, price=Decimal("400"))
        cover(self.pro, self.koram)
        ProviderProfile.objects.filter(pk=self.pro.pk).update(experience_years=9, is_available=True, bio="Nine years", languages=["English"])

        self.url = reverse("service-provider-list", args=[self.tap.pk])

    def ids(self, res):
        return [r["provider"] for r in res.data["results"]]

    def test_lists_live_offers_with_public_fields_only(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)
        row = next(r for r in res.data["results"] if r["provider"] == self.pro.pk)
        self.assertEqual(
            (row["display_name"], row["price"], row["pricing_type"], row["experience_years"], row["is_online"], row["languages"], row["bio"]),
            ("Pro Plumbers", "400.00", "fixed", 9, True, ["English"], "Nine years"),
        )
        self.assertEqual(set(row), {"id", "provider", "display_name", "bio", "experience_years", "languages", "is_online", "price", "pricing_type", "estimated_duration_minutes"})
        for secret in ("phone", "email", "full_name", "user"):
            self.assertNotIn(secret, row)

    def test_default_order_is_online_first_then_cheapest(self):
        self.assertEqual(self.ids(self.client.get(self.url)), [self.pro.pk, self.cheap.pk])

    def test_ordering_parameter(self):
        order = lambda o: self.ids(self.client.get(self.url, {"ordering": o}))
        self.assertEqual(order("price"), [self.cheap.pk, self.pro.pk])
        self.assertEqual(order("-price"), [self.pro.pk, self.cheap.pk])
        self.assertEqual(order("experience"), [self.cheap.pk, self.pro.pk])
        self.assertEqual(order("-experience"), [self.pro.pk, self.cheap.pk])
        self.assertEqual(self.client.get(self.url, {"ordering": "rating"}).status_code, 400)

    def test_city_and_area_filters(self):
        city = lambda c: self.ids(self.client.get(self.url, {"city": c}))
        self.assertEqual(sorted(city(self.blr.pk)), sorted([self.pro.pk, self.cheap.pk]))
        self.assertEqual(city(self.che.pk), [])
        area = lambda a, **kw: self.ids(self.client.get(self.url, {"area": a, **kw}))
        self.assertEqual(area(self.indira.pk), [self.cheap.pk])
        self.assertEqual(area(self.koram.pk), [self.pro.pk])
        self.assertEqual(area(self.adyar.pk), [])
        self.assertEqual(area(self.indira.pk, city=self.blr.pk), [self.cheap.pk])

    def test_bad_filters_are_400(self):
        inactive = Area.objects.create(city=self.blr, name="Old", pincode="560001", is_active=False)
        for params in ({"city": "abc"}, {"city": 9999}, {"area": "abc"}, {"area": 9999}, {"area": inactive.pk},
                       {"area": self.adyar.pk, "city": self.blr.pk}):                       # area not in that city
            self.assertEqual(self.client.get(self.url, params).status_code, 400, params)

    def test_only_approved_providers_with_active_offers_are_listed(self):
        for status in (Status.PENDING, Status.UNDER_REVIEW, Status.REJECTED, Status.SUSPENDED):
            ProviderProfile.objects.filter(pk=self.pro.pk).update(approval_status=status)
            self.assertEqual(self.ids(self.client.get(self.url)), [self.cheap.pk], status)
        ProviderProfile.objects.filter(pk=self.pro.pk).update(approval_status=Status.APPROVED)
        self.pro.provider_services.update(is_active=False)
        self.assertEqual(self.ids(self.client.get(self.url)), [self.cheap.pk])

    def test_a_provider_offering_something_else_is_not_listed(self):
        other = make_provider("+919600000003")
        offer(other, self.other_service)
        cover(other, self.indira)
        self.assertNotIn(other.pk, self.ids(self.client.get(self.url)))

    def test_unknown_or_inactive_service_is_404(self):
        self.assertEqual(self.client.get(reverse("service-provider-list", args=[9999])).status_code, 404)
        self.tap.is_active = False
        self.tap.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_pagination_and_stale_token(self):
        res = self.client.get(self.url, {"page_size": 1})
        self.assertEqual((res.data["count"], len(res.data["results"])), (2, 1))
        self.assertIsNotNone(res.data["next"])
        self.assertEqual(self.client.get(self.url, HTTP_AUTHORIZATION="Bearer expired.garbage.token").status_code, 200)


class PublicProviderPageTests(APITestCase):
    def setUp(self):
        city = City.objects.create(name="Bengaluru", state="Karnataka")
        self.area = Area.objects.create(city=city, name="Indiranagar", pincode="560038")
        old = Area.objects.create(city=city, name="Old", pincode="560001", is_active=False)
        category = Category.objects.create(name="Plumbing")
        self.tap = Service.objects.create(category=category, name="Tap repair", base_price=300)
        self.retired = Service.objects.create(category=category, name="Retired", base_price=100, is_active=False)

        self.provider = make_provider("+919700000001", business_name="Pro Plumbers", email="pro@example.com")
        offer(self.provider, self.tap, price=Decimal("350"))
        offer(self.provider, self.retired)
        offer(self.provider, Service.objects.create(category=category, name="Switched off", base_price=10), active=False)
        cover(self.provider, self.area, old)

    def test_public_page_shows_live_services_and_areas_without_contact_details(self):
        res = self.client.get(reverse("public-provider-detail", args=[self.provider.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["display_name"], "Pro Plumbers")
        self.assertEqual([(s["name"], s["price"]) for s in res.data["services"]], [("Tap repair", "350.00")])
        self.assertEqual([a["name"] for a in res.data["areas"]], ["Indiranagar"])
        for secret in ("phone", "email", "full_name", "user", "approval_status", "internal_admin_note"):
            self.assertNotIn(secret, res.data)

    def test_only_approved_providers_have_a_public_page(self):
        pending = make_provider("+919700000002", status=Status.PENDING)
        self.assertEqual(self.client.get(reverse("public-provider-detail", args=[pending.pk])).status_code, 404)
        ProviderProfile.objects.filter(pk=self.provider.pk).update(approval_status=Status.SUSPENDED)
        self.assertEqual(self.client.get(reverse("public-provider-detail", args=[self.provider.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("public-provider-detail", args=[9999])).status_code, 404)

    def test_stale_token_does_not_break_it(self):
        res = self.client.get(reverse("public-provider-detail", args=[self.provider.pk]), HTTP_AUTHORIZATION="Bearer expired.garbage.token")
        self.assertEqual(res.status_code, 200)
