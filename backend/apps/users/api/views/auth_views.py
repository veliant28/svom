import hashlib
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.api.serializers import (
    LoginRequestSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterRequestSerializer,
    UserSummarySerializer,
)
from apps.users.models import User
from apps.core.services import get_configured_frontend_base_url, send_configured_mail
from apps.core.services.email_delivery import sanitize_smtp_error_message

logger = logging.getLogger(__name__)


def _build_frontend_url(request, path: str) -> str:
    configured_base_url = get_configured_frontend_base_url()
    origin = request.headers.get("Origin", "").strip().rstrip("/")
    base_url = configured_base_url or origin
    if not base_url:
        base_url = request.build_absolute_uri("/").rstrip("/")
    return f"{base_url}{path}"


def _password_reset_email_content(locale: str, reset_url: str) -> tuple[str, str]:
    messages = {
        User.LANGUAGE_RU: (
            "Восстановление пароля SVOM",
            (
                "Мы получили запрос на восстановление пароля аккаунта SVOM.\n\n"
                f"Откройте ссылку, чтобы задать новый пароль:\n{reset_url}\n\n"
                "Если вы не запрашивали восстановление, просто проигнорируйте письмо."
            ),
        ),
        User.LANGUAGE_UK: (
            "Відновлення пароля SVOM",
            (
                "Ми отримали запит на відновлення пароля акаунта SVOM.\n\n"
                f"Відкрийте посилання, щоб задати новий пароль:\n{reset_url}\n\n"
                "Якщо ви не запитували відновлення, просто проігноруйте лист."
            ),
        ),
        User.LANGUAGE_EN: (
            "SVOM password reset",
            (
                "We received a request to reset your SVOM account password.\n\n"
                f"Open this link to set a new password:\n{reset_url}\n\n"
                "If you did not request this, ignore this email."
            ),
        ),
    }
    return messages.get(locale, messages[User.LANGUAGE_UK])


def _hashed_cache_part(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _password_reset_request_allowed(request, email: str) -> bool:
    timeout = int(getattr(settings, "PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS", 60) or 60)
    remote_addr = str(request.META.get("REMOTE_ADDR") or "unknown").strip()
    key = f"password-reset:{_hashed_cache_part(f'{email.lower()}:{remote_addr}')}"
    try:
        return bool(cache.add(key, "1", timeout=timeout))
    except Exception:
        logger.warning("Password reset rate-limit cache is unavailable", exc_info=False)
        return True


class AuthLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserSummarySerializer(user).data,
            }
        )


class AuthRegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserSummarySerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AuthLogoutAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_token = request.auth
        if isinstance(auth_token, Token):
            auth_token.delete()
        else:
            Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSummarySerializer(request.user).data)


class ProfileUpdateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSummarySerializer(request.user).data)


class PasswordChangeAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        locale = serializer.validated_data["locale"]

        if not _password_reset_request_allowed(request, email):
            return Response(status=status.HTTP_204_NO_CONTENT)

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = _build_frontend_url(request, f"/{locale}/reset-password/{uid}/{token}")
            subject, message = _password_reset_email_content(locale, reset_url)
            try:
                send_configured_mail(
                    subject=subject,
                    message=message,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as exc:
                logger.warning(
                    "Password reset email delivery failed safely: error_type=%s message=%s",
                    exc.__class__.__name__,
                    sanitize_smtp_error_message(exc),
                )

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        Token.objects.filter(user=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
