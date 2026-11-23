from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

pincode_validator = RegexValidator(r"^\d{6}$", "Enter a valid 6-digit pincode.")


class City(models.Model):
    """A city the platform operates in. Customers pick a city first."""

    name = models.CharField(max_length=100)
    state = models.CharField(max_length=60)
    district = models.CharField(max_length=60, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cities"
        ordering = ["name"]
        verbose_name_plural = "cities"
        constraints = [
            models.UniqueConstraint(fields=["state", "name"], name="uniq_city_state_name")
        ]

    def __str__(self):
        return f"{self.name}, {self.state}"


class Area(models.Model):
    """A locality (usually one pincode) inside a city. Customer addresses and
    provider service coverage both point at areas."""

    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="areas")
    name = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6, validators=[pincode_validator])
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "areas"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["city", "name", "pincode"], name="uniq_area_city_name_pincode"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.pincode}), {self.city.name}"


class CustomerAddress(models.Model):
    """A saved service address. Deleting archives it (is_active=False) so that
    future bookings that point at it keep their history."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="customer_addresses")
    label = models.CharField(max_length=30, default="Home")
    address_line = models.CharField(max_length=255)
    landmark = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_addresses"
        ordering = ["-is_default", "-created_at", "-id"]
        verbose_name_plural = "customer addresses"
        constraints = [
            # The database itself guarantees at most one default address per user.
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True, is_active=True),
                name="uniq_default_address_per_user",
            )
        ]

    def __str__(self):
        return f"{self.label}: {self.address_line}"
