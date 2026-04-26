from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from apps.users.models import User

from .phone_utils import normalize_profile_phone


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class RegisterRequestSerializer(serializers.ModelSerializer):
    password = serializers.CharField(trim_whitespace=False, min_length=8, write_only=True)

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "preferred_language",
        )
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": False, "allow_blank": True},
            "middle_name": {"required": False, "allow_blank": True},
            "phone": {"required": True},
            "preferred_language": {"required": False},
        }

    def validate_email(self, value: str) -> str:
        normalized = User.objects.normalize_email(value).strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate_first_name(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("First name is required.")
        return normalized

    def validate_last_name(self, value: str) -> str:
        return value.strip()

    def validate_middle_name(self, value: str) -> str:
        return value.strip()

    def validate_phone(self, value: str) -> str:
        compact_value = normalize_profile_phone(value)
        if not compact_value:
            raise serializers.ValidationError("Phone is required.")
        return compact_value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    locale = serializers.ChoiceField(choices=User.LANGUAGE_CHOICES, required=False, default=User.LANGUAGE_UK)

    def validate_email(self, value: str) -> str:
        return User.objects.normalize_email(value).strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False, min_length=8, write_only=True)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "Password reset link is invalid or expired."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Password reset link is invalid or expired."})

        validate_password(attrs["new_password"], user)
        attrs["user"] = user
        return attrs
