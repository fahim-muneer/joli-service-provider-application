from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomerRegistrationView,
    LoginView,
    LogoutAllView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    ProviderRegistrationView,
)

urlpatterns = [
    path("register/customer/", CustomerRegistrationView.as_view(), name="register-customer"),
    path("register/provider/", ProviderRegistrationView.as_view(), name="register-provider"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout-all"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("profile/", ProfileView.as_view(), name="profile"),
]