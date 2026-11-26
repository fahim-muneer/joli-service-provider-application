from .models import Notification


def create_notification(
    *,
    user,
    notification_type,
    title,
    body,
    booking=None,
):
    """
    Create an in-app notification for a user.
    """

    return Notification.objects.create(
        user=user,
        booking=booking,
        type=notification_type,
        title=title,
        body=body,
    )