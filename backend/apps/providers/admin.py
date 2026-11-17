from django.contrib import admin

from .models import (
    ProviderArea,
    ProviderDocument,
    ProviderProfile,
    ProviderService,
    ProviderStatusHistory,
)


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "business_name", "user", "approval_status", "is_available", "applied_at")
    list_filter = ("approval_status", "is_available")
    search_fields = ("business_name", "user__full_name", "user__phone")


@admin.register(ProviderDocument)
class ProviderDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "document_type", "status", "uploaded_at")
    list_filter = ("document_type", "status")
    exclude = ("document_file",)  # never expose the stored path in the Django admin


admin.site.register(ProviderService)
admin.site.register(ProviderArea)
admin.site.register(ProviderStatusHistory)
