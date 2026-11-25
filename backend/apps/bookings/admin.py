from django.contrib import admin

from .models import Booking, BookingRequest, BookingStatusLog


class RequestInline(admin.TabularInline):
    model = BookingRequest
    extra = 0
    readonly_fields = ("provider", "status", "offered_at", "expires_at", "responded_at")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "service_name", "customer", "assigned_provider", "scheduled_at", "status")
    list_filter = ("status", "payment_mode")
    search_fields = ("reference", "customer__phone", "service_name")
    inlines = [RequestInline]


admin.site.register(BookingStatusLog)
