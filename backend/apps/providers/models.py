import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.services.models import Service

from .storage import PrivateStorage


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


def document_upload_path(instance, filename):
    """Random, unguessable name; the original file name is kept in `original_name`."""
    return f"provider_documents/{instance.provider_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class ProviderDocument(models.Model):
    class DocumentType(models.TextChoices):
        ID_PROOF = "id_proof", "ID proof"
        ADDRESS_PROOF = "address_proof", "Address proof"
        BUSINESS_LICENSE = "business_license", "Business licence"
        SKILL_CERTIFICATE = "skill_certificate", "Skill certificate"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    document_file = models.FileField(
        upload_to=document_upload_path, storage=PrivateStorage(), max_length=255
    )
    original_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_provider_documents",
    )
    rejection_reason = models.TextField(blank=True)
    admin_remark = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "provider_documents"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document_type} for provider {self.provider_id} ({self.status})"


class ProviderStatusHistory(models.Model):
    """Every approval-status change, who made it and why (audit trail)."""

    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="status_history"
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "provider_status_history"
        ordering = ["-changed_at", "-id"]
        verbose_name_plural = "provider status history"


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
