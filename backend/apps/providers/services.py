from .models import ProviderProfile


def create_provider_profile(*, user, business_name=None) -> ProviderProfile:
    """New providers always start as 'pending' and unavailable."""
    return ProviderProfile.objects.create(
        user=user,
        business_name=(business_name or "").strip(),
    )