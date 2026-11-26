"""All provider writes and the approval workflow live here."""
from datetime import timedelta

from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.locations.models import Area

from . import selectors
from .models import (
    ProviderArea,
    ProviderAvailability,
    ProviderDocument,
    ProviderProfile,
    ProviderService,
    ProviderStatusHistory,
)

Status = ProviderProfile.ApprovalStatus
DocStatus = ProviderDocument.Status

# Allowed approval-status changes: (from, to)
TRANSITIONS = {
    (Status.PENDING, Status.UNDER_REVIEW),     # provider submits
    (Status.REJECTED, Status.UNDER_REVIEW),    # provider fixes things and resubmits
    (Status.UNDER_REVIEW, Status.APPROVED),    # admin approves
    (Status.UNDER_REVIEW, Status.REJECTED),    # admin rejects (reason required)
    (Status.APPROVED, Status.SUSPENDED),       # admin suspends (reason required)
    (Status.SUSPENDED, Status.APPROVED),       # admin reinstates
}


def create_provider_profile(*, user, business_name=None) -> ProviderProfile:
    """New providers always start as 'pending' and unavailable."""
    return ProviderProfile.objects.create(
        user=user,
        business_name=(business_name or "").strip(),
    )


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------

def _lock(profile) -> ProviderProfile:
    """Re-read the row with a lock so two simultaneous actions can't both win."""
    return ProviderProfile.objects.select_for_update().select_related("user").get(pk=profile.pk)


def _transition(profile, to, *, by, reason="", note="", **fields):
    current = profile.approval_status

    if (current, to) not in TRANSITIONS:
        raise ValidationError({
            "detail": f"A provider that is '{current}' cannot become '{to}'."
        })

    for name, value in fields.items():
        setattr(profile, name, value)

    profile.approval_status = to
    profile.save()

    ProviderStatusHistory.objects.create(
        provider=profile,
        changed_by=by,
        from_status=current,
        to_status=to,
        reason=reason,
        internal_note=note,
    )

    notification_data = None

    if to == Status.APPROVED and current == Status.SUSPENDED:
        notification_data = (
            Notification.Type.PROVIDER_REINSTATED,
            "Account reinstated",
            "Your Joli provider account has been reinstated. "
            "You can now continue providing services.",
        )

    elif to == Status.APPROVED:
        notification_data = (
            Notification.Type.PROVIDER_APPROVED,
            "Account approved",
            "Congratulations! Your Joli provider account has been approved.",
        )

    elif to == Status.REJECTED:
        notification_data = (
            Notification.Type.PROVIDER_REJECTED,
            "Application rejected",
            f"Your provider application was rejected. Reason: {reason}",
        )

    elif to == Status.SUSPENDED:
        notification_data = (
            Notification.Type.PROVIDER_SUSPENDED,
            "Account suspended",
            f"Your Joli provider account has been suspended. Reason: {reason}",
        )

    if notification_data:
        notification_type, title, body = notification_data

        transaction.on_commit(
            lambda: create_notification(
                user=profile.user,
                notification_type=notification_type,
                title=title,
                body=body,
            )
        )

    return profile

@transaction.atomic
def submit_for_review(*, profile, user) -> ProviderProfile:
    profile = _lock(profile)
    if profile.approval_status not in selectors.SUBMITTABLE_STATUSES:
        raise ValidationError({"detail": "This application cannot be submitted right now."})
    blockers = selectors.submission_blockers(profile)
    if blockers:
        raise ValidationError({"detail": blockers})
    return _transition(profile, Status.UNDER_REVIEW, by=user, rejection_reason="")


@transaction.atomic
def approve_provider(*, profile, admin, note="") -> ProviderProfile:
    profile = _lock(profile)
    # Approving is only for applications under review. (A suspended provider is
    # brought back with reinstate_provider, which must not skip the document check.)
    if profile.approval_status != Status.UNDER_REVIEW:
        raise ValidationError({"detail": "Only applications that are under review can be approved."})
    if not selectors.has_approved_required_document(profile):
        raise ValidationError({"detail": "Approve at least one ID proof document first."})
    return _transition(
        profile, Status.APPROVED, by=admin, note=note,
        reviewed_by=admin, reviewed_at=timezone.now(), rejection_reason="",
    )


@transaction.atomic
def reject_provider(*, profile, admin, reason) -> ProviderProfile:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    profile = _lock(profile)
    return _transition(
        profile, Status.REJECTED, by=admin, reason=reason,
        reviewed_by=admin, reviewed_at=timezone.now(), rejection_reason=reason,
    )


@transaction.atomic
def suspend_provider(*, profile, admin, reason) -> ProviderProfile:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    profile = _lock(profile)
    return _transition(
        profile, Status.SUSPENDED, by=admin, reason=reason,
        reviewed_by=admin, reviewed_at=timezone.now(), is_available=False,
    )


@transaction.atomic
def reinstate_provider(*, profile, admin, note="") -> ProviderProfile:
    profile = _lock(profile)
    if profile.approval_status != Status.SUSPENDED:
        raise ValidationError({"detail": "Only suspended providers can be reinstated."})
    return _transition(
        profile, Status.APPROVED, by=admin, note=note,
        reviewed_by=admin, reviewed_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@transaction.atomic
def add_document(*, profile, document_type, file, expires_at=None) -> ProviderDocument:
    return ProviderDocument.objects.create(
        provider=profile,
        document_type=document_type,
        document_file=file,
        original_name=file.name[:255],
        expires_at=expires_at,
    )


@transaction.atomic
def delete_document(*, document) -> None:
    if document.status == DocStatus.APPROVED:
        raise ValidationError({"detail": "An approved document cannot be deleted."})
    storage, name = document.document_file.storage, document.document_file.name
    document.delete()
    transaction.on_commit(lambda: storage.delete(name))  # remove the file only if the row is gone


@transaction.atomic
def review_document(*, document, admin, decision, reason="", remark="") -> ProviderDocument:
    if decision not in (DocStatus.APPROVED, DocStatus.REJECTED):
        raise ValidationError({"decision": "Must be 'approved' or 'rejected'."})
    reason = (reason or "").strip()
    if decision == DocStatus.REJECTED and not reason:
        raise ValidationError({"reason": "A reason is required when rejecting a document."})
    document.status = decision
    document.rejection_reason = reason if decision == DocStatus.REJECTED else ""
    document.admin_remark = remark or ""
    document.reviewed_by = admin
    document.reviewed_at = timezone.now()
    document.save()
    return document


# ---------------------------------------------------------------------------
# Services a provider offers
# ---------------------------------------------------------------------------

@transaction.atomic
def set_provider_service(
    *, profile, service, custom_price=None, pricing_type=None, estimated_duration_minutes=None
):
    """Offer a catalogue service. Offering one the provider previously switched
    off simply turns it back on. Returns (provider_service, created)."""
    if not (service.is_active and service.category.is_active):
        raise ValidationError({"service": "This service is not available."})

    values = {
        "custom_price": custom_price if custom_price is not None else service.base_price,
        "pricing_type": pricing_type or service.pricing_type,
        "estimated_duration_minutes": estimated_duration_minutes or service.estimated_duration_minutes,
    }
    obj, created = ProviderService.objects.get_or_create(
        provider=profile, service=service, defaults={**values, "is_active": True}
    )
    if not created:
        for name, value in values.items():
            # keep what the provider had unless they sent a new value
            if name == "custom_price" and custom_price is None:
                continue
            if name == "pricing_type" and not pricing_type:
                continue
            if name == "estimated_duration_minutes" and not estimated_duration_minutes:
                continue
            setattr(obj, name, value)
        obj.is_active = True
        obj.save()
    return obj, created


def deactivate_provider_service(*, provider_service) -> None:
    """'Delete' = switch off; rows stay because future bookings will point at them."""
    if provider_service.is_active:
        provider_service.is_active = False
        provider_service.save(update_fields=["is_active"])


# ---------------------------------------------------------------------------
# Areas a provider covers
# ---------------------------------------------------------------------------

@transaction.atomic
def replace_areas(*, profile, area_ids) -> None:
    wanted = set(area_ids)
    valid = set(
        Area.objects.filter(pk__in=wanted, is_active=True, city__is_active=True).values_list("pk", flat=True)
    )
    missing = wanted - valid
    if missing:
        raise ValidationError({"areas": f"Unknown or inactive area ids: {sorted(missing)}"})

    ProviderArea.objects.filter(provider=profile).exclude(area_id__in=valid).delete()
    existing = set(ProviderArea.objects.filter(provider=profile).values_list("area_id", flat=True))
    ProviderArea.objects.bulk_create(
        [ProviderArea(provider=profile, area_id=pk) for pk in sorted(valid - existing)]
    )


# ---------------------------------------------------------------------------
# Availability: online switch + schedule
# ---------------------------------------------------------------------------

MAX_DAYS_AHEAD = 90


@transaction.atomic
def set_online(*, profile, online: bool) -> ProviderProfile:
    profile = _lock(profile)
    if online and profile.approval_status != Status.APPROVED:
        raise ValidationError({"detail": "Only approved providers can go online."})
    profile.is_available = online
    profile.save(update_fields=["is_available", "updated_at"])
    return profile


@transaction.atomic
def add_windows(*, profile, dates, start_time, end_time, is_available=True):
    """Create the same time window on one or more dates, all or nothing."""
    if end_time <= start_time:
        raise ValidationError({"end_time": "Must be after start_time."})
    profile = _lock(profile)  # serialise concurrent edits of one provider's schedule
    today = timezone.localdate()
    last_day = today + timedelta(days=MAX_DAYS_AHEAD)
    unique = sorted(set(dates))
    problems = []
    for day in unique:
        if day < today:
            problems.append(f"{day}: this date is in the past.")
        elif day > last_day:
            problems.append(f"{day}: more than {MAX_DAYS_AHEAD} days ahead.")
        elif selectors.overlapping_windows(
            profile, day, start_time, end_time, is_available=is_available
        ).exists():
            problems.append(f"{day}: overlaps an existing window.")
    if problems:
        raise ValidationError({"dates": problems})
    ProviderAvailability.objects.bulk_create(
        [
            ProviderAvailability(
                provider=profile, available_date=day, start_time=start_time,
                end_time=end_time, is_available=is_available,
            )
            for day in unique
        ]
    )
    return list(
        ProviderAvailability.objects.filter(
            provider=profile, available_date__in=unique, start_time=start_time,
            end_time=end_time, is_available=is_available,
        )
    )


@transaction.atomic
def update_window(*, window, start_time=None, end_time=None, is_available=None):
    profile = _lock(window.provider)
    if window.available_date < timezone.localdate():
        raise ValidationError({"detail": "A window in the past cannot be changed."})
    new_start = start_time if start_time is not None else window.start_time
    new_end = end_time if end_time is not None else window.end_time
    new_flag = window.is_available if is_available is None else is_available
    if new_end <= new_start:
        raise ValidationError({"end_time": "Must be after start_time."})
    if selectors.overlapping_windows(
        profile, window.available_date, new_start, new_end,
        is_available=new_flag, exclude_pk=window.pk,
    ).exists():
        raise ValidationError({"detail": "This overlaps another window of the same kind."})
    window.start_time, window.end_time, window.is_available = new_start, new_end, new_flag
    window.save()
    return window


def delete_window(*, window) -> None:
    window.delete()
