"""Writes for customer addresses."""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import CustomerAddress

MAX_ADDRESSES = 10  # active addresses per customer


def _active(user_id):
    return CustomerAddress.objects.filter(user_id=user_id, is_active=True)


@transaction.atomic
def create_address(*, user, is_default=False, **fields) -> CustomerAddress:
    existing = list(_active(user.pk).select_for_update())  # lock this customer's rows
    if len(existing) >= MAX_ADDRESSES:
        raise ValidationError({"detail": f"You can save at most {MAX_ADDRESSES} addresses."})
    make_default = is_default or not existing          # the first address is the default
    if make_default:
        _active(user.pk).filter(is_default=True).update(is_default=False)
    return CustomerAddress.objects.create(user=user, is_default=make_default, **fields)


@transaction.atomic
def update_address(*, address, **fields) -> CustomerAddress:
    list(_active(address.user_id).select_for_update())
    want_default = fields.pop("is_default", None)
    if want_default is False and address.is_default:
        raise ValidationError(
            {"is_default": "Choose another address as the default instead."}
        )
    for name, value in fields.items():
        setattr(address, name, value)
    if want_default and not address.is_default:
        # clear the old default BEFORE setting the new one (one default per user)
        _active(address.user_id).filter(is_default=True).update(is_default=False)
        address.is_default = True
    address.save()
    return address


@transaction.atomic
def archive_address(*, address) -> None:
    """'Delete' = archive. If it was the default, the newest remaining address takes over."""
    list(_active(address.user_id).select_for_update())
    was_default = address.is_default
    address.is_active = False
    address.is_default = False
    address.save(update_fields=["is_active", "is_default", "updated_at"])
    if was_default:
        successor = _active(address.user_id).order_by("-created_at", "-id").first()
        if successor:
            successor.is_default = True
            successor.save(update_fields=["is_default", "updated_at"])
