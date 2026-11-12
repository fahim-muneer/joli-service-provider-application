from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from django.contrib.auth import get_user_model

from . import services
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneVerificationConfirmSerializer,
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


class PhoneVerificationSendThrottle(UserRateThrottle):
    scope = "phone_verification_send"
    rate = "5/hour"  # per user


class PhoneVerificationConfirmThrottle(UserRateThrottle):
    scope = "phone_verification_confirm"
    rate = "20/hour"  # per user; per-code attempts are limited separately


class PhoneVerificationSendView(APIView):
    """(Re)send the verification code. A first code is already sent at sign-up."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [PhoneVerificationSendThrottle]

    def post(self, request):
        services.send_phone_verification(user=request.user)
        return Response({"detail": "Verification code sent."})


class PhoneVerificationConfirmView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PhoneVerificationConfirmThrottle]

    def post(self, request):
        serializer = PhoneVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.confirm_phone_verification(
            user=request.user, otp=serializer.validated_data["otp"]
        )
        return Response(
            {"detail": "Phone number verified.", "user": ProfileSerializer(user).data}
        )


class ChangePasswordThrottle(UserRateThrottle):
    scope = "change_password"
    rate = "10/hour"  # per user; stops password guessing with a stolen access token


class ChangePasswordView(APIView):
    """Change the password of the logged-in user.

    All of the user's sessions are ended, and a NEW token pair is returned so the
    current device stays signed in. The frontend must replace its stored tokens."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ChangePasswordThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        refresh = LoginSerializer.get_token(request.user)  # issued AFTER the revoke
        return Response(
            {
                "detail": "Password changed.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class ProfileView(generics.RetrieveAPIView):
    """Current user's profile, for any role."""

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user