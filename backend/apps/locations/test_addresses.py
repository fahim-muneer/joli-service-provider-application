from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .models import Area, City, CustomerAddress
from .services import MAX_ADDRESSES

User = get_user_model()
PW = "Str0ng-Passw0rd!"


def make_user(role, phone):
    return User.objects.create_user(phone=phone, password=PW, full_name="T", role=role)


class AddressTests(APITestCase):
    def setUp(self):
        self.customer = make_user(User.Role.CUSTOMER, "+919400000001")
        self.other = make_user(User.Role.CUSTOMER, "+919400000002")
        self.city = City.objects.create(name="Bengaluru", state="Karnataka")
        self.area = Area.objects.create(city=self.city, name="Indiranagar", pincode="560038")
        self.area2 = Area.objects.create(city=self.city, name="Koramangala", pincode="560034")
        self.client.force_authenticate(self.customer)
        self.list_url = reverse("address-list")

    def body(self, **extra):
        return {"label": "Home", "address_line": "12 Test Street, Block A", "area": self.area.pk, **extra}

    def add(self, **extra):
        return self.client.post(self.list_url, self.body(**extra), format="json")

    def defaults(self, user=None):
        return CustomerAddress.objects.filter(user=user or self.customer, is_active=True, is_default=True)

    # ---------- access ----------

    def test_only_customers_can_use_addresses(self):
        self.assertEqual(APIClient().get(self.list_url).status_code, 401)
        for role, phone in ((User.Role.PROVIDER, "+919400000003"), (User.Role.ADMIN, "+919400000004")):
            self.client.force_authenticate(make_user(role, phone))
            self.assertEqual(self.client.get(self.list_url).status_code, 403)
            self.assertEqual(self.add().status_code, 403)

    # ---------- create ----------

    def test_first_address_becomes_default_and_shows_area_details(self):
        res = self.add(landmark="Near the park", latitude="12.9716000", longitude="77.5946000")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["is_default"])
        self.assertEqual(
            (res.data["area_name"], res.data["pincode"], res.data["city_name"], res.data["city"]),
            ("Indiranagar", "560038", "Bengaluru", self.city.pk),
        )
        self.assertEqual(res.data["landmark"], "Near the park")

    def test_later_addresses_are_not_default_unless_asked(self):
        self.add()
        second = self.add(label="Office")
        self.assertFalse(second.data["is_default"])
        third = self.add(label="Parents", is_default=True)
        self.assertTrue(third.data["is_default"])
        self.assertEqual(list(self.defaults().values_list("pk", flat=True)), [third.data["id"]])

    def test_validation(self):
        inactive_area = Area.objects.create(city=self.city, name="Old", pincode="560001", is_active=False)
        hidden = City.objects.create(name="Hidden", state="X", is_active=False)
        in_hidden = Area.objects.create(city=hidden, name="Z", pincode="111111")
        cases = {
            "unknown area": {"area": 9999},
            "inactive area": {"area": inactive_area.pk},
            "area in inactive city": {"area": in_hidden.pk},
            "short address": {"address_line": "abc"},
            "label too long": {"label": "x" * 31},
            "lat without lng": {"latitude": "12.97"},
            "lng without lat": {"longitude": "77.59"},
            "lat out of range": {"latitude": "91", "longitude": "77"},
            "lng out of range": {"latitude": "12", "longitude": "181"},
        }
        for label, extra in cases.items():
            self.assertEqual(self.add(**extra).status_code, 400, label)
        missing = self.client.post(self.list_url, {"label": "Home"}, format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertFalse(CustomerAddress.objects.exists())

    def test_address_limit_counts_only_active_addresses(self):
        for i in range(MAX_ADDRESSES):
            self.assertEqual(self.add(label=f"A{i}").status_code, 201)
        self.assertEqual(self.add(label="one too many").status_code, 400)
        first = CustomerAddress.objects.filter(user=self.customer).order_by("id").first()
        self.client.delete(reverse("address-detail", args=[first.pk]))
        self.assertEqual(self.add(label="fits now").status_code, 201)

    # ---------- read ----------

    def test_list_is_default_first_and_private(self):
        a = self.add(label="A").data["id"]
        b = self.add(label="B", is_default=True).data["id"]
        self.client.force_authenticate(self.other)
        self.add(label="Not mine")
        self.client.force_authenticate(self.customer)
        res = self.client.get(self.list_url)
        self.assertEqual([x["id"] for x in res.data], [b, a])
        self.assertTrue(res.data[0]["is_default"])

    def test_other_customers_addresses_are_404(self):
        mine = self.add().data["id"]
        self.client.force_authenticate(self.other)
        for call, args in ((self.client.get, ()), (self.client.delete, ())):
            self.assertEqual(call(reverse("address-detail", args=[mine])).status_code, 404)
        self.assertEqual(self.client.patch(reverse("address-detail", args=[mine]), {"label": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.post(reverse("address-default", args=[mine])).status_code, 404)

    # ---------- update ----------

    def test_patch_fields_and_area(self):
        pk = self.add(latitude="12.9716000", longitude="77.5946000").data["id"]
        url = reverse("address-detail", args=[pk])
        res = self.client.patch(url, {"label": "Flat", "landmark": "Opposite the bank", "area": self.area2.pk}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["label"], res.data["area_name"], res.data["landmark"]), ("Flat", "Koramangala", "Opposite the bank"))
        self.assertEqual(self.client.patch(url, {"latitude": "13.00"}, format="json").status_code, 200)  # pair already stored
        self.assertEqual(self.client.patch(url, {"area": 9999}, format="json").status_code, 400)

    def test_patch_cannot_unset_the_default_but_can_move_it(self):
        a = self.add(label="A").data["id"]
        b = self.add(label="B").data["id"]
        self.assertEqual(self.client.patch(reverse("address-detail", args=[a]), {"is_default": False}, format="json").status_code, 400)
        res = self.client.patch(reverse("address-detail", args=[b]), {"is_default": True}, format="json")
        self.assertTrue(res.data["is_default"])
        self.assertEqual(list(self.defaults().values_list("pk", flat=True)), [b])

    def test_default_endpoint(self):
        self.add(label="A")
        b = self.add(label="B").data["id"]
        res = self.client.post(reverse("address-default", args=[b]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_default"])
        self.assertEqual(self.defaults().count(), 1)
        self.assertEqual(self.client.post(reverse("address-default", args=[b])).status_code, 200)  # idempotent

    # ---------- delete (archive) ----------

    def test_delete_archives_and_promotes_the_newest_remaining(self):
        a = self.add(label="A").data["id"]            # default
        b = self.add(label="B").data["id"]
        c = self.add(label="C").data["id"]
        self.assertEqual(self.client.delete(reverse("address-detail", args=[a])).status_code, 204)
        archived = CustomerAddress.objects.get(pk=a)
        self.assertFalse(archived.is_active)
        self.assertFalse(archived.is_default)
        res = self.client.get(self.list_url)
        self.assertEqual({x["id"] for x in res.data}, {b, c})
        self.assertEqual([x["id"] for x in res.data if x["is_default"]], [c])      # newest became default
        self.assertEqual(self.client.get(reverse("address-detail", args=[a])).status_code, 404)
        self.assertEqual(self.client.delete(reverse("address-detail", args=[a])).status_code, 404)

    def test_deleting_a_non_default_keeps_the_default(self):
        a = self.add(label="A").data["id"]
        b = self.add(label="B").data["id"]
        self.client.delete(reverse("address-detail", args=[b]))
        self.assertEqual(list(self.defaults().values_list("pk", flat=True)), [a])

    def test_deleting_the_last_address_leaves_none_and_the_next_one_is_default_again(self):
        a = self.add().data["id"]
        self.client.delete(reverse("address-detail", args=[a]))
        self.assertEqual(self.client.get(self.list_url).data, [])
        self.assertTrue(self.add(label="Fresh").data["is_default"])

    # ---------- database guarantee ----------

    def test_database_refuses_two_default_addresses(self):
        CustomerAddress.objects.create(user=self.customer, area=self.area, address_line="first one", is_default=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerAddress.objects.create(user=self.customer, area=self.area, address_line="second one", is_default=True)
        # an archived default does not count, and another customer may have their own default
        CustomerAddress.objects.create(user=self.other, area=self.area, address_line="theirs one", is_default=True)
