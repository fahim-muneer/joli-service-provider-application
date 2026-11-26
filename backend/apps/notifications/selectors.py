"""Read-only queries for notifications."""

from .models import Notification


def list_user_notifications(user, *, unread_only=False):
    """
    Return notifications belonging only to the authenticated user.
    """

    qs = Notification.objects.filter(user=user)

    if unread_only:
        qs = qs.filter(is_read=False)

    return qs.order_by("-created_at")


def get_user_notification(user, pk):
    """
    Retrieve one notification belonging to the authenticated user.
    """

    return Notification.objects.filter(
        user=user,
        pk=pk,
    ).first()


def get_unread_count(user):
    """
    Return the number of unread notifications for a user.
    """

    return Notification.objects.filter(
        user=user,
        is_read=False,
    ).count()