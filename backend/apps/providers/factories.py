"""Small helpers to build provider data (used by tests and the demo seed command)."""
from django.contrib.auth import get_user_model

from .models import ProviderArea, ProviderProfile, ProviderService

User = get_user_model()


def make_provider(
    phone,
    *,
    status=ProviderProfile.ApprovalStatus.APPROVED,
    business_name="Demo Provider",
    password="Str0ng-Passw0rd!",
):
    user = User.objects.create_user(
        phone=phone, password=password, full_name=business_name, role=User.Role.PROVIDER
    )
    return ProviderProfile.objects.create(
        user=user, approval_status=status, business_name=business_name
    )


def offer(provider, service, *, price=None, active=True):
    obj, _ = ProviderService.objects.get_or_create(
        provider=provider,
        service=service,
        defaults={
            "custom_price": price if price is not None else service.base_price,
            "pricing_type": service.pricing_type,
            "estimated_duration_minutes": service.estimated_duration_minutes,
            "is_active": active,
        },
    )
    return obj


def cover(provider, *areas):
    for area in areas:
        ProviderArea.objects.get_or_create(provider=provider, area=area)
