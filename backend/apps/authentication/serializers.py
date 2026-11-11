from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import exceptions, serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.utils import normalize_phone

from . import services

User = get_user_model()


class PhoneField(serializers.CharField):
    """Normalizes to +91XXXXXXXXXX *before* validators run, so the unique check
    compares like with like ('98765 43210' and '+919876543210' are the same)."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


class EmailAddressField(serializers.EmailField):
    """Strips and lowercases *before* validators run, so format and uniqueness
    checks see the same value that gets stored."""

    def to_internal_value(self, data):
        return super().to_internal_value(data).strip().lower()


def unique_email_validator():
    return UniqueValidator(
        queryset=User.objects.all(),
        lookup="iexact",
        message="A user with this email already exists.",
    )


class RegistrationSerializer(serializers.ModelSerializer):
    """Shared by customer and provider sign-up. The role is NOT a request field:
    the view passes it in through serializer.save(role=...)."""

    phone = PhoneField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with this phone number already exists.",
            )
        ]
    )
    email = EmailAddressField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=254,
        validators=[unique_email_validator()],
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "email",
            "role",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id", "role"]

    def validate_email(self, value):
        # Store NULL instead of "" so the unique constraint allows many users
        # without an email. (Needs email = EmailField(null=True, blank=True).)
        return value or None

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return services.register_user(**validated_data)


class ProviderRegistrationSerializer(RegistrationSerializer):
    # Providers must give an email: admins use it for approval/onboarding contact.
    email = EmailAddressField(
        required=True,
        allow_null=False,
        allow_blank=False,
        max_length=254,
        validators=[unique_email_validator()],
    )
    business_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=150
    )

    class Meta(RegistrationSerializer.Meta):
        fields = RegistrationSerializer.Meta.fields + ["business_name"]


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "email",
            "role",
            "is_phone_verified",
            "date_joined",
        ]
        read_only_fields = fields


class LoginSerializer(TokenObtainPairSerializer):
    """POST {"phone", "password", "portal"?}.

    `portal` is optional: each frontend sends its own name ("customer",
    "provider" or "admin") so an account can only sign in on its own app."""

    portal = serializers.ChoiceField(
        choices=["customer", "provider", "admin"], required=False, write_only=True
    )

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        portal = attrs.get("portal")
        try:  # so "98765 43210" logs in the same account as "+919876543210"
            attrs[self.username_field] = normalize_phone(attrs.get(self.username_field))
        except ValueError:
            pass  # authenticate() below will fail with the normal 401
        data = super().validate(attrs)  # raises 401 for bad credentials/inactive users
        if portal and self.user.role != portal:
            raise exceptions.PermissionDenied(
                "This account cannot sign in on this portal."
            )
        data["user"] = ProfileSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    phone = PhoneField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    phone = PhoneField()
    otp = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."})
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs