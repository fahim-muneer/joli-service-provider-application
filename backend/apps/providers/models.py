from django.conf import settings
from django.db import models

from apps.services.models import Service


class ProviderProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile",
    )
    business_name = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    languages = models.JSONField(default=list, blank=True)

    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_provider_profiles",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    internal_admin_note = models.TextField(blank=True)

    # Providers become bookable only after approval AND switching this on.
    is_available = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "provider_profiles"

    def __str__(self):
        return f"{self.business_name or self.user.full_name} ({self.approval_status})"


class ProviderService(models.Model):
    """A service a provider offers, with their own price and duration."""

    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="provider_services"
    )
    service = models.ForeignKey(
        "services.Service", on_delete=models.PROTECT, related_name="provider_services"
    )
    custom_price = models.DecimalField(max_digits=10, decimal_places=2)
    pricing_type = models.CharField(max_length=12, choices=Service.PricingType.choices)
    estimated_duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "provider_services"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "service"], name="uniq_provider_service"
            )
        ]

    def __str__(self):
        return f"{self.provider_id} offers {self.service_id}"


class ProviderArea(models.Model):
    """An area a provider is willing to travel to."""

    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="service_areas"
    )
    area = models.ForeignKey(
        "locations.Area", on_delete=models.PROTECT, related_name="provider_areas"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "provider_areas"
        constraints = [
            models.UniqueConstraint(fields=["provider", "area"], name="uniq_provider_area")
        ]

    def __str__(self):
        return f"{self.provider_id} covers {self.area_id}"
