from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Area, City
from apps.providers.factories import cover, make_provider, offer
from apps.providers.models import ProviderProfile, ProviderService

from .models import Category, Service

User = get_user_model()
PW = "Str0ng-Passw0rd!"


class CatalogTests(APITestCase):
    def setUp(self):
        self.blr = City.objects.create(name="Bengaluru", state="Karnataka")
        self.che = City.objects.create(name="Chennai", state="Tamil Nadu")
        self.blr_area = Area.objects.create(city=self.blr, name="Indiranagar", pincode="560038")
        self.che_area = Area.objects.create(city=self.che, name="Adyar", pincode="600020")

        self.plumbing = Category.objects.create(name="Plumbing", display_order=2)
        self.cleaning = Category.objects.create(name="Cleaning", display_order=1)
        self.tap = Service.objects.create(
            category=self.plumbing, name="Tap repair", description="Fix leaking taps", base_price=Decimal("299")
        )
        self.clean = Service.objects.create(
            category=self.cleaning, name="Deep cleaning", base_price=Decimal("1999"), pricing_type="fixed"
        )
        # Only Bengaluru has a live provider, and only for the tap service.
        self.provider = make_provider("+919100000001")
        offer(self.provider, self.tap)
        cover(self.provider, self.blr_area)

    def names(self, res):
        data = res.data["results"] if isinstance(res.data, dict) else res.data
        return [s["name"] for s in data]

    # ---------- categories ----------

    def test_categories_are_ordered_and_hide_inactive(self):
        Category.objects.create(name="Hidden", is_active=False)
        res = self.client.get(reverse("category-list"))
        self.assertEqual([c["name"] for c in res.data], ["Cleaning", "Plumbing"])  # display_order
        self.assertEqual(
            set(res.data[0]), {"id", "name", "slug", "icon", "description", "display_order"}
        )

    def test_categories_filtered_by_city(self):
        res = self.client.get(reverse("category-list"), {"city": self.blr.pk})
        self.assertEqual([c["name"] for c in res.data], ["Plumbing"])
        res = self.client.get(reverse("category-list"), {"city": self.che.pk})
        self.assertEqual(res.data, [])

    # ---------- services list ----------

    def test_service_list_without_city_shows_all_active_services(self):
        res = self.client.get(reverse("service-list"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(self.names(res), ["Deep cleaning", "Tap repair"])  # by category order
        first = res.data["results"][0]
        self.assertEqual(first["category"]["name"], "Cleaning")
        self.assertEqual(first["base_price"], "1999.00")

    def test_city_filter_returns_only_services_available_there(self):
        self.assertEqual(self.names(self.client.get(reverse("service-list"), {"city": self.blr.pk})), ["Tap repair"])
        self.assertEqual(self.names(self.client.get(reverse("service-list"), {"city": self.che.pk})), [])

    def test_unapproved_provider_does_not_make_a_service_available(self):
        pending = make_provider("+919100000002", status=ProviderProfile.ApprovalStatus.PENDING)
        offer(pending, self.clean)
        cover(pending, self.blr_area)
        res = self.client.get(reverse("service-list"), {"city": self.blr.pk})
        self.assertEqual(self.names(res), ["Tap repair"])

    def test_availability_requires_provider_service_and_area_to_be_active(self):
        url, params = reverse("service-list"), {"city": self.blr.pk}

        ProviderService.objects.update(is_active=False)
        self.assertEqual(self.names(self.client.get(url, params)), [])
        ProviderService.objects.update(is_active=True)
        self.assertEqual(self.names(self.client.get(url, params)), ["Tap repair"])

        self.blr_area.is_active = False
        self.blr_area.save()
        self.assertEqual(self.names(self.client.get(url, params)), [])

    def test_availability_ignores_the_providers_online_toggle(self):
        self.assertFalse(self.provider.is_available)  # defaults to off, still listed
        res = self.client.get(reverse("service-list"), {"city": self.blr.pk})
        self.assertEqual(self.names(res), ["Tap repair"])

    def test_suspended_provider_removes_availability(self):
        self.provider.approval_status = ProviderProfile.ApprovalStatus.SUSPENDED
        self.provider.save()
        res = self.client.get(reverse("service-list"), {"city": self.blr.pk})
        self.assertEqual(self.names(res), [])

    def test_inactive_service_or_category_is_hidden_everywhere(self):
        self.tap.is_active = False
        self.tap.save()
        self.assertEqual(self.names(self.client.get(reverse("service-list"))), ["Deep cleaning"])
        self.assertEqual(self.client.get(reverse("service-detail", args=[self.tap.pk])).status_code, 404)

        self.cleaning.is_active = False
        self.cleaning.save()
        self.assertEqual(self.names(self.client.get(reverse("service-list"))), [])

    def test_filter_by_category_id_slug_and_search(self):
        url = reverse("service-list")
        self.assertEqual(self.names(self.client.get(url, {"category": self.plumbing.pk})), ["Tap repair"])
        self.assertEqual(self.names(self.client.get(url, {"category": "cleaning"})), ["Deep cleaning"])
        self.assertEqual(self.names(self.client.get(url, {"search": "leaking"})), ["Tap repair"])
        self.assertEqual(self.names(self.client.get(url, {"search": "nothing-matches"})), [])

    def test_filters_combine(self):
        res = self.client.get(
            reverse("service-list"), {"category": "plumbing", "city": self.blr.pk, "search": "tap"}
        )
        self.assertEqual(self.names(res), ["Tap repair"])
        res = self.client.get(reverse("service-list"), {"category": "cleaning", "city": self.blr.pk})
        self.assertEqual(self.names(res), [])

    def test_pagination(self):
        res = self.client.get(reverse("service-list"), {"page_size": 1})
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertIsNotNone(res.data["next"])

    def test_bad_city_parameter_is_a_400(self):
        inactive = City.objects.create(name="Gone", state="X", is_active=False)
        for bad in ["abc", "99999", str(inactive.pk)]:
            for name in ("service-list", "category-list"):
                res = self.client.get(reverse(name), {"city": bad})
                self.assertEqual(res.status_code, 400, f"{name} {bad}")
                self.assertIn("city", res.data)

    # ---------- detail ----------

    def test_service_detail_reports_availability_for_a_city(self):
        url = reverse("service-detail", args=[self.tap.pk])
        self.assertIsNone(self.client.get(url).data["available_in_city"])
        self.assertTrue(self.client.get(url, {"city": self.blr.pk}).data["available_in_city"])
        self.assertFalse(self.client.get(url, {"city": self.che.pk}).data["available_in_city"])

    def test_stale_token_does_not_break_public_endpoints(self):
        res = self.client.get(reverse("service-list"), HTTP_AUTHORIZATION="Bearer expired.garbage.token")
        self.assertEqual(res.status_code, 200)


class AdminCatalogTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone="+919111111111", password=PW, full_name="Admin", role=User.Role.ADMIN
        )
        self.customer = User.objects.create_user(
            phone="+919333333333", password=PW, full_name="Cust", role=User.Role.CUSTOMER
        )

    def test_permissions(self):
        for name in ("admin-category-list", "admin-service-list"):
            url = reverse(name)
            self.assertEqual(self.client.get(url).status_code, 401, name)
            self.client.force_authenticate(self.customer)
            self.assertEqual(self.client.get(url).status_code, 403, name)
            self.client.force_authenticate(self.admin)
            self.assertEqual(self.client.get(url).status_code, 200, name)
            self.client = APIClient()

    def test_category_slug_is_generated_and_unique(self):
        self.client.force_authenticate(self.admin)
        url = reverse("admin-category-list")
        first = self.client.post(url, {"name": "Home Cleaning"}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["slug"], "home-cleaning")
        second = self.client.post(url, {"name": "Home-Cleaning"}, format="json")  # same slug base
        self.assertEqual(second.data["slug"], "home-cleaning-2")
        dup_name = self.client.post(url, {"name": "Home Cleaning"}, format="json")
        self.assertEqual(dup_name.status_code, 400)

    def test_service_crud_validation_and_archive(self):
        self.client.force_authenticate(self.admin)
        category = Category.objects.create(name="Plumbing")
        url = reverse("admin-service-list")
        body = {"category": category.pk, "name": "Tap repair", "base_price": "299.00"}

        res = self.client.post(url, body, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["pricing_type"], "fixed")
        self.assertEqual(res.data["estimated_duration_minutes"], 60)
        service_id = res.data["id"]

        self.assertEqual(self.client.post(url, body, format="json").status_code, 400)            # duplicate
        self.assertEqual(self.client.post(url, {**body, "name": "B", "base_price": "-1"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {**body, "name": "C", "estimated_duration_minutes": 0}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {**body, "name": "D", "pricing_type": "nope"}, format="json").status_code, 400)

        patch = self.client.patch(
            reverse("admin-service-detail", args=[service_id]), {"base_price": "349.00"}, format="json"
        )
        self.assertEqual(patch.data["base_price"], "349.00")

        self.assertEqual(self.client.delete(reverse("admin-service-detail", args=[service_id])).status_code, 204)
        self.assertFalse(Service.objects.get(pk=service_id).is_active)       # archived, row kept
        self.client = APIClient()
        self.assertEqual(self.client.get(reverse("service-list")).data["count"], 0)

    def test_admin_lists_include_inactive_and_support_filters(self):
        plumbing = Category.objects.create(name="Plumbing")
        electrical = Category.objects.create(name="Electrical")
        Service.objects.create(category=plumbing, name="Tap", base_price=1)
        Service.objects.create(category=plumbing, name="Pipe", base_price=1, is_active=False)
        Service.objects.create(category=electrical, name="Fan", base_price=1)
        self.client.force_authenticate(self.admin)
        url = reverse("admin-service-list")
        self.assertEqual(self.client.get(url).data["count"], 3)
        self.assertEqual(self.client.get(url, {"is_active": "false"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"category": plumbing.pk}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"search": "fan"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"category": "abc"}).status_code, 400)
