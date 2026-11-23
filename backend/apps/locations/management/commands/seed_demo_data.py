from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.locations.models import Area, City
from apps.providers.factories import cover, make_provider, offer
from apps.providers.models import ProviderProfile
from apps.services.models import Category, Service

CITIES = {
    ("Bengaluru", "Karnataka"): [("Indiranagar", "560038"), ("Koramangala", "560034")],
    ("Chennai", "Tamil Nadu"): [("Adyar", "600020"), ("T Nagar", "600017")],
}

# Artwork keys (see frontend/src/assets/figma/README.md): the frontend shows icon-<key> / banner-<key>.
CATEGORY_ICONS = {"Plumbing": "plumber", "Electrical": "electrician", "Cleaning": "cleaning"}

CATALOG = {
    "Plumbing": [
        ("Tap repair", "fixed", "299.00", 45),
        ("Pipe leak fix", "hourly", "399.00", 60),
    ],
    "Electrical": [
        ("Fan installation", "fixed", "349.00", 45),
        ("Wiring inspection", "inspection", "199.00", 30),
    ],
    "Cleaning": [("Deep home cleaning", "fixed", "1999.00", 180)],
}

User = get_user_model()

DEMO_PASSWORD = "Demo@12345"
APPROVED_PHONE = "+919100000001"
PENDING_PHONE = "+919100000002"
CUSTOMER_PHONE = "+919100000003"
ADMIN_PHONE = "+919100000010"


class Command(BaseCommand):
    help = "Create demo cities, areas, categories, services and two demo providers (DEBUG only; safe to re-run)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_data only runs with DEBUG=True.")

        areas = {}
        for (city_name, state), area_list in CITIES.items():
            city, _ = City.objects.get_or_create(name=city_name, state=state)
            for name, pincode in area_list:
                area, _ = Area.objects.get_or_create(city=city, name=name, pincode=pincode)
                areas.setdefault(city_name, []).append(area)

        services = {}
        for order, (cat_name, items) in enumerate(CATALOG.items(), start=1):
            category, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={"display_order": order, "icon": CATEGORY_ICONS.get(cat_name, "")},
            )
            if not category.icon and cat_name in CATEGORY_ICONS:   # also fix rows from an earlier run
                category.icon = CATEGORY_ICONS[cat_name]
                category.save(update_fields=["icon"])
            for name, pricing, price, minutes in items:
                service, _ = Service.objects.get_or_create(
                    category=category,
                    name=name,
                    defaults={
                        "base_price": price,
                        "pricing_type": pricing,
                        "estimated_duration_minutes": minutes,
                    },
                )
                services.setdefault(cat_name, []).append(service)

        # An approved provider: visible. Serves Bengaluru, offers everything.
        approved = ProviderProfile.objects.filter(user__phone=APPROVED_PHONE).first() or make_provider(
            APPROVED_PHONE, business_name="Demo Approved Provider", password=DEMO_PASSWORD,
            email="approved.provider@example.com", phone_verified=True,
        )
        for group in services.values():
            for service in group:
                offer(approved, service)
        cover(approved, *areas["Bengaluru"])

        # A pending provider: must NOT make Chennai or Cleaning "available".
        pending = ProviderProfile.objects.filter(user__phone=PENDING_PHONE).first() or make_provider(
            PENDING_PHONE,
            status=ProviderProfile.ApprovalStatus.PENDING,
            business_name="Demo Pending Provider",
            password=DEMO_PASSWORD,
            email="pending.provider@example.com",
            phone_verified=True,
        )
        offer(pending, services["Cleaning"][0])
        cover(pending, *areas["Chennai"])

        # A customer and an admin, so every role can be tested straight away.
        if not User.objects.filter(phone=CUSTOMER_PHONE).exists():
            User.objects.create_user(
                phone=CUSTOMER_PHONE, password=DEMO_PASSWORD, full_name="Demo Customer",
                role=User.Role.CUSTOMER, is_phone_verified=True,
            )
        if not User.objects.filter(phone=ADMIN_PHONE).exists():
            User.objects.create_user(
                phone=ADMIN_PHONE, password=DEMO_PASSWORD, full_name="Demo Admin",
                role=User.Role.ADMIN, is_staff=True, is_phone_verified=True,
            )

        self.stdout.write(self.style.SUCCESS("Demo data ready. Logins (password for all: %s):" % DEMO_PASSWORD))
        self.stdout.write(
            f"  admin     {ADMIN_PHONE}  (portal: admin)\n"
            f"  customer  {CUSTOMER_PHONE}  (portal: customer)\n"
            f"  provider  {APPROVED_PHONE}  approved, serves Bengaluru (portal: provider)\n"
            f"  provider  {PENDING_PHONE}  pending, not visible to customers"
        )
