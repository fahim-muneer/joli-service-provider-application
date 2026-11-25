from rest_framework import serializers

from .models import Area, City, CustomerAddress


# ---- public (customer / provider apps) ----

class CityPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name", "state", "district"]
        read_only_fields = fields


class AreaPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = ["id", "name", "pincode", "latitude", "longitude"]
        read_only_fields = fields


# ---- admin portal ----

class AdminCitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = [
            "id", "name", "state", "district", "latitude", "longitude",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AdminAreaSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = Area
        fields = [
            "id", "city", "city_name", "name", "pincode", "latitude", "longitude",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "city_name", "created_at"]


# ---- customer addresses ----

class CustomerAddressSerializer(serializers.ModelSerializer):
    area = serializers.PrimaryKeyRelatedField(
        queryset=Area.objects.filter(is_active=True, city__is_active=True)
    )
    area_name = serializers.CharField(source="area.name", read_only=True)
    pincode = serializers.CharField(source="area.pincode", read_only=True)
    city = serializers.IntegerField(source="area.city_id", read_only=True)
    city_name = serializers.CharField(source="area.city.name", read_only=True)

    class Meta:
        model = CustomerAddress
        fields = [
            "id", "label", "address_line", "landmark", "area", "area_name", "pincode",
            "city", "city_name", "latitude", "longitude", "is_default", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"address_line": {"min_length": 5}}

    def validate(self, attrs):
        # Coordinates come as a pair. On PATCH, combine with what is already stored.
        current = self.instance
        lat = attrs.get("latitude", getattr(current, "latitude", None))
        lng = attrs.get("longitude", getattr(current, "longitude", None))
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": "Send latitude and longitude together (or neither)."}
            )
        return attrs
