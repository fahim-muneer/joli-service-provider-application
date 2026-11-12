
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = (
        "phone",
        "full_name",
        "email",
        "role",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "role",
        "is_active",
        "is_staff",
        "is_phone_verified",
    )

    search_fields = ("phone", "full_name", "email")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Personal information", {
            "fields": ("full_name", "email", "role")
        }),
        ("Verification", {
            "fields": ("is_phone_verified", "is_email_verified")
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Account status", {
            "fields": ("suspended_at", "suspension_reason")
        }),
        ("Important dates", {
            "fields": ("last_login", "date_joined", "updated_at")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "phone",
                "full_name",
                "email",
                "role",
                "password1",
                "password2",
                "is_staff",
                "is_superuser",
            ),
        }),
    )

    readonly_fields = ("last_login", "date_joined", "updated_at")

