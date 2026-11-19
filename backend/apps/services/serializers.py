from rest_framework import serializers

from apps.providers import selectors as provider_selectors

from .models import Category, Service


# ---- public ----

class CategoryPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "description", "display_order"]
        read_only_fields = fields


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class ServicePublicSerializer(serializers.ModelSerializer):
    category = CategoryBriefSerializer(read_only=True)

    class Meta:
        model = Service
        fields = [
            "id", "category", "name", "description", "image",
            "base_price", "pricing_type", "estimated_duration_minutes",
        ]
        read_only_fields = fields


class ServiceDetailSerializer(ServicePublicSerializer):
    """Adds `available_in_city` when the request carries ?city=<id>
    (true/false), otherwise null."""

    available_in_city = serializers.SerializerMethodField()

    class Meta(ServicePublicSerializer.Meta):
        fields = ServicePublicSerializer.Meta.fields + ["available_in_city"]
        read_only_fields = fields

    def get_available_in_city(self, obj):
        city_id = self.context.get("city_id")
        if city_id is None:
            return None
        return provider_selectors.available_service_ids(city_id).filter(service_id=obj.pk).exists()


# ---- admin portal ----

class AdminCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "icon", "description", "display_order",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "slug", "created_at"]


class AdminServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id", "category", "category_name", "name", "description", "image",
            "base_price", "pricing_type", "estimated_duration_minutes",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "category_name", "created_at"]
