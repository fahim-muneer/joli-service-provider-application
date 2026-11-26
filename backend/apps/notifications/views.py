from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """
    GET: List the authenticated user's notifications.
    Optional query parameter: ?unread=true
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        unread_only = (
            self.request.query_params.get("unread", "").lower() == "true"
        )

        return selectors.list_user_notifications(
            self.request.user,
            unread_only=unread_only,
        )


class UnreadNotificationCountView(APIView):
    """
    GET: Return the authenticated user's unread notification count.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = selectors.get_unread_count(request.user)

        return Response({"unread_count": count})


class NotificationMarkReadView(APIView):
    """
    POST: Mark one notification as read.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = selectors.get_user_notification(
            request.user,
            pk,
        )

        if notification is None:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()

            notification.save(
                update_fields=["is_read", "read_at"]
            )

        return Response(
            NotificationSerializer(notification).data
        )


class NotificationMarkAllReadView(APIView):
    """
    POST: Mark all unread notifications belonging to the user as read.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        now = timezone.now()

        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=now,
        )

        return Response({
            "message": "All notifications marked as read.",
            "updated_count": updated_count,
        })