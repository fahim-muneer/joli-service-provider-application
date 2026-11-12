from rest_framework import serializers

from .models import Area, City


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
