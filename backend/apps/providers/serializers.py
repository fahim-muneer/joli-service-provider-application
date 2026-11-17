from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.services.models import Service

from . import selectors
from .models import (
    ProviderArea,
    ProviderDocument,
    ProviderProfile,
    ProviderService,
    ProviderStatusHistory,
)
from .validators import validate_document_file


# ------------------------- provider: profile -------------------------

class ProviderProfileSerializer(serializers.ModelSerializer):
    """The provider's own profile. Only the four profile fields can be edited;
    status, availability and review fields are read-only."""

    languages = serializers.ListField(
        child=serializers.CharField(max_length=30), max_length=10, required=False
    )
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_phone_verified = serializers.BooleanField(source="user.is_phone_verified", read_only=True)
    can_submit = serializers.SerializerMethodField()
    submission_blockers = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = [
            "id", "business_name", "bio", "experience_years", "languages",
            "full_name", "phone", "email", "is_phone_verified",
            "approval_status", "rejection_reason", "is_available", "applied_at",
            "can_submit", "submission_blockers",
        ]
        read_only_fields = [
            "id", "approval_status", "rejection_reason", "is_available", "applied_at",
        ]

    def get_can_submit(self, obj):
        return selectors.can_submit(obj)

    def get_submission_blockers(self, obj):
        return selectors.submission_blockers(obj)


# ------------------------- documents -------------------------

class ProviderDocumentSerializer(serializers.ModelSerializer):
    """What a provider sees. The stored file is never exposed, only a
    permission-checked download_url."""

    file_route = "provider-document-file"
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ProviderDocument
        fields = [
            "id", "document_type", "original_name", "status", "rejection_reason",
            "uploaded_at", "reviewed_at", "expires_at", "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        return reverse(self.file_route, args=[obj.pk], request=self.context.get("request"))


class AdminProviderDocumentSerializer(ProviderDocumentSerializer):
    file_route = "admin-provider-document-file"

    class Meta(ProviderDocumentSerializer.Meta):
        fields = ProviderDocumentSerializer.Meta.fields + ["admin_remark"]
        read_only_fields = fields


class ProviderDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=ProviderDocument.DocumentType.choices)
    file = serializers.FileField(validators=[validate_document_file])
    expires_at = serializers.DateField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("This document has already expired.")
        return value


# ------------------------- services offered -------------------------

class ProviderServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    category_name = serializers.CharField(source="service.category.name", read_only=True)
    base_price = serializers.DecimalField(
        source="service.base_price", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProviderService
        fields = [
            "id", "service", "service_name", "category_name", "base_price",
            "custom_price", "pricing_type", "estimated_duration_minutes", "is_active",
        ]
        read_only_fields = fields


class ProviderServiceCreateSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.select_related("category"))
    custom_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )
    pricing_type = serializers.ChoiceField(choices=Service.PricingType.choices, required=False)
    estimated_duration_minutes = serializers.IntegerField(min_value=1, required=False)


class ProviderServiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderService
        fields = ["custom_price", "pricing_type", "estimated_duration_minutes", "is_active"]
        extra_kwargs = {
            "custom_price": {"min_value": Decimal("0")},
            "estimated_duration_minutes": {"min_value": 1},
        }


# ------------------------- areas covered -------------------------

class ProviderAreaSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="area_id", read_only=True)
    name = serializers.CharField(source="area.name", read_only=True)
    pincode = serializers.CharField(source="area.pincode", read_only=True)
    city = serializers.IntegerField(source="area.city_id", read_only=True)
    city_name = serializers.CharField(source="area.city.name", read_only=True)

    class Meta:
        model = ProviderArea
        fields = ["id", "name", "pincode", "city", "city_name"]
        read_only_fields = fields


class ProviderAreasUpdateSerializer(serializers.Serializer):
    areas = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=200, allow_empty=True
    )


# ------------------------- admin portal -------------------------

class StatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True, default=None)

    class Meta:
        model = ProviderStatusHistory
        fields = [
            "id", "from_status", "to_status", "reason", "internal_note",
            "changed_by_name", "changed_at",
        ]
        read_only_fields = fields


class AdminProviderListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_phone_verified = serializers.BooleanField(source="user.is_phone_verified", read_only=True)
    documents_count = serializers.IntegerField(read_only=True)
    pending_documents_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProviderProfile
        fields = [
            "id", "full_name", "phone", "email", "is_phone_verified", "business_name",
            "approval_status", "applied_at", "documents_count", "pending_documents_count",
        ]
        read_only_fields = fields


class AdminProviderDetailSerializer(ProviderProfileSerializer):
    documents = AdminProviderDocumentSerializer(many=True, read_only=True)
    services = ProviderServiceSerializer(source="provider_services", many=True, read_only=True)
    areas = ProviderAreaSerializer(source="service_areas", many=True, read_only=True)
    status_history = StatusHistorySerializer(many=True, read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.full_name", read_only=True, default=None)

    class Meta(ProviderProfileSerializer.Meta):
        fields = ProviderProfileSerializer.Meta.fields + [
            "internal_admin_note", "reviewed_by_name", "reviewed_at",
            "documents", "services", "areas", "status_history",
        ]
        read_only_fields = fields


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class NoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class DocumentReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected"])
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    remark = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
