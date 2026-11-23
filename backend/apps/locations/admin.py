from django.contrib import admin

from .models import Area, City


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "district", "is_active")
    list_filter = ("state", "is_active")
    search_fields = ("name", "state", "district")


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "pincode", "city", "is_active")
    list_filter = ("city", "is_active")
    search_fields = ("name", "pincode")
