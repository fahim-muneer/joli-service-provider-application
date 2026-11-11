from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from django.contrib.auth import get_user_model

from . import services
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    ProviderRegistrationSerializer,
    RegistrationSerializer,
)

User = get_user_model()


class _BaseRegistrationView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    # A stale/expired token in the header must not break sign-up.
    authentication_classes = []
    role = None  # set by subclasses; never read from the request body

    def perform_create(self, serializer):
        serializer.save(role=self.role)


class CustomerRegistrationView(_BaseRegistrationView):
    serializer_class = RegistrationSerializer
    role = User.Role.CUSTOMER


class ProviderRegistrationView(_BaseRegistrationView):
    serializer_class = ProviderRegistrationSerializer
    role = User.Role.PROVIDER


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class LogoutView(APIView):
    """Blacklist one refresh token (this device). Needs no access token, so a
    user whose access token already expired can still log out."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(APIView):
    """Blacklist every refresh token of the current user (all devices)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        services.revoke_all_sessions(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestThrottle(AnonRateThrottle):
    scope = "password_reset_request"
    rate = "5/hour"  # per IP


class PasswordResetConfirmThrottle(AnonRateThrottle):
    scope = "password_reset_confirm"
    rate = "20/hour"  # per IP; per-code attempts are limited separately


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(phone=serializer.validated_data["phone"])
        # Same answer whether or not the number is registered.
        return Response(
            {"detail": "If an account exists for this number, a verification code has been sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_password_reset(
            phone=serializer.validated_data["phone"],
            otp=serializer.validated_data["otp"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password reset successful. Please log in."})


class ProfileView(generics.RetrieveAPIView):
    """Current user's profile, for any role."""

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user