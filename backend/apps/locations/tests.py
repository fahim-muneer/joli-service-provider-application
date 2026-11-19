import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.providers.factories import cover, make_provider, offer
from apps.providers.models import ProviderProfile
from apps.services.models import Category, Service

from .models import Area, City

User = get_user_model()
PW = "Str0ng-Passw0rd!"


def make_user(role, phone):
    return User.objects.create_user(phone=phone, password=PW, full_name="Test", role=role)


class PublicLocationTests(APITestCase):
    def setUp(self):
        self.blr = City.objects.create(name="Bengaluru", state="Karnataka", district="Bengaluru Urban")
        self.che = City.objects.create(name="Chennai", state="Tamil Nadu")
        self.hidden = City.objects.create(name="Hidden", state="Nowhere", is_active=False)
        self.indira = Area.objects.create(city=self.blr, name="Indiranagar", pincode="560038")
        self.old = Area.objects.create(city=self.blr, name="Old Area", pincode="560001", is_active=False)

        category = Category.objects.create(name="Plumbing")
        self.tap = Service.objects.create(category=category, name="Tap repair", base_price=299)
        provider = make_provider("+919100000001")
        offer(provider, self.tap)
        cover(provider, self.indira)

    def test_city_list_shows_only_active_cities_with_public_fields(self):
        res = self.client.get(reverse("city-list"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual([c["name"] for c in res.data], ["Bengaluru", "Chennai"])
        self.assertEqual(set(res.data[0]), {"id", "name", "state", "district"})

    def test_available_filter_keeps_only_cities_with_live_coverage(self):
        res = self.client.get(reverse("city-list"), {"available": "true"})
        self.assertEqual([c["name"] for c in res.data], ["Bengaluru"])

    def test_available_filter_ignores_unapproved_providers(self):
        pending = make_provider("+919100000002", status=ProviderProfile.ApprovalStatus.PENDING)
        che_area = Area.objects.create(city=self.che, name="Adyar", pincode="600020")
        offer(pending, self.tap)
        cover(pending, che_area)
        res = self.client.get(reverse("city-list"), {"available": "true"})
        self.assertEqual([c["name"] for c in res.data], ["Bengaluru"])

    def test_available_filter_needs_an_active_service_and_active_area(self):
        self.indira.is_active = False
        self.indira.save()
        res = self.client.get(reverse("city-list"), {"available": "true"})
        self.assertEqual(res.data, [])

    def test_area_list_shows_only_active_areas(self):
        res = self.client.get(reverse("city-area-list", args=[self.blr.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual([a["name"] for a in res.data], ["Indiranagar"])

    def test_area_list_404_for_unknown_or_inactive_city(self):
        self.assertEqual(self.client.get(reverse("city-area-list", args=[9999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("city-area-list", args=[self.hidden.pk])).status_code, 404)

    def test_stale_token_does_not_break_public_endpoints(self):
        res = self.client.get(reverse("city-list"), HTTP_AUTHORIZATION="Bearer expired.garbage.token")
        self.assertEqual(res.status_code, 200)


class AdminLocationTests(APITestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN, "+919111111111")
        self.customer = make_user(User.Role.CUSTOMER, "+919333333333")

    def test_permissions(self):
        url = reverse("admin-city-list")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"name": "X", "state": "Y"}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_city_crud_and_archive(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            reverse("admin-city-list"), {"name": "Kochi", "state": "Kerala"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        city_id = res.data["id"]
        dup = self.client.post(
            reverse("admin-city-list"), {"name": "Kochi", "state": "Kerala"}, format="json"
        )
        self.assertEqual(dup.status_code, 400)

        patch = self.client.patch(
            reverse("admin-city-detail", args=[city_id]), {"district": "Ernakulam"}, format="json"
        )
        self.assertEqual(patch.data["district"], "Ernakulam")

        self.assertEqual(self.client.delete(reverse("admin-city-detail", args=[city_id])).status_code, 204)
        self.assertFalse(City.objects.get(pk=city_id).is_active)      # archived, not deleted
        self.client = APIClient()
        public = self.client.get(reverse("city-list"))
        self.assertEqual(public.data, [])                              # hidden from customers

    def test_admin_list_includes_inactive_and_filters(self):
        City.objects.create(name="A", state="S")
        City.objects.create(name="B", state="S", is_active=False)
        self.client.force_authenticate(self.admin)
        res = self.client.get(reverse("admin-city-list"))
        self.assertEqual(res.data["count"], 2)
        res = self.client.get(reverse("admin-city-list"), {"is_active": "false"})
        self.assertEqual([c["name"] for c in res.data["results"]], ["B"])

    def test_admin_area_validation_and_filter(self):
        city = City.objects.create(name="Kochi", state="Kerala")
        other = City.objects.create(name="Other", state="Kerala")
        self.client.force_authenticate(self.admin)
        url = reverse("admin-area-list")

        bad = self.client.post(url, {"city": city.pk, "name": "X", "pincode": "12345"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("pincode", bad.data)

        ok = self.client.post(url, {"city": city.pk, "name": "Edappally", "pincode": "682024"}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.data["city_name"], "Kochi")
        dup = self.client.post(url, {"city": city.pk, "name": "Edappally", "pincode": "682024"}, format="json")
        self.assertEqual(dup.status_code, 400)

        Area.objects.create(city=other, name="Elsewhere", pincode="682001")
        res = self.client.get(url, {"city": city.pk})
        self.assertEqual([a["name"] for a in res.data["results"]], ["Edappally"])
        self.assertEqual(self.client.get(url, {"city": "abc"}).status_code, 400)


class SeedCommandTests(APITestCase):
    @override_settings(DEBUG=True)
    def test_seed_is_idempotent_and_produces_a_bookable_city(self):
        call_command("seed_demo_data", stdout=io.StringIO())
        call_command("seed_demo_data", stdout=io.StringIO())  # second run must not duplicate anything
        self.assertEqual(City.objects.count(), 2)
        self.assertEqual(Service.objects.count(), 5)
        res = self.client.get(reverse("city-list"), {"available": "true"})
        self.assertEqual([c["name"] for c in res.data], ["Bengaluru"])  # Chennai only has a pending provider

    def test_seed_refuses_to_run_without_debug(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo_data", stdout=io.StringIO())
