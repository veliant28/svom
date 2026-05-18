from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse

from django.conf import settings as django_settings
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.autodb.models import AutoDbTranslationSettings
from apps.autodb.selectors import (
    get_autodb_remote_settings,
    get_autodb_translation_settings,
    has_autodb_remote_settings_table,
    has_autodb_translation_settings_table,
)
from apps.autodb.services.remote_client import AutoDbProRemoteClient, AutoDbProRemoteClientError
from apps.autodb.services.remote_config import AutoDbRemoteConfigError
from apps.backoffice.api.serializers import CheckoutMethodSettingsSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.commerce.services import get_checkout_method_settings
from apps.commerce.services.liqpay import get_liqpay_settings
from apps.commerce.services.monobank import get_monobank_settings
from apps.commerce.services.novapay import get_novapay_settings
from apps.commerce.services.vchasno_kasa import get_vchasno_kasa_settings, has_vchasno_kasa_settings_table
from apps.core.selectors import get_email_delivery_settings, get_telegram_settings
from apps.seo.selectors import get_seo_site_settings
from apps.supplier_imports.selectors.integration_selectors import get_supplier_integration_by_code


TOGGLE_PAYMENT_MONOBANK = "payment.monobank"
TOGGLE_PAYMENT_NOVAPAY = "payment.novapay"
TOGGLE_PAYMENT_LIQPAY = "payment.liqpay"
TOGGLE_PAYMENT_COD = "payment.cash_on_delivery"
TOGGLE_DELIVERY_PICKUP = "delivery.pickup"
TOGGLE_DELIVERY_NOVA_POSHTA = "delivery.nova_poshta"
TOGGLE_DELIVERY_COURIER = "delivery.courier"
TOGGLE_SUPPLIER_UTR = "supplier.utr"
TOGGLE_SUPPLIER_GPL = "supplier.gpl"
TOGGLE_VCHASNO_KASA = "integration.vchasno_kasa"
TOGGLE_SEO = "integration.seo"
TOGGLE_EMAIL = "integration.email"
TOGGLE_TELEGRAM_MASTER = "integration.telegram"
TOGGLE_TELEGRAM_OPS = "integration.telegram_ops"
TOGGLE_TELEGRAM_SUPPORT = "integration.telegram_support"
TOGGLE_TELEGRAM_SYSTEM = "integration.telegram_system"

SUPPORTED_TOGGLE_KEYS = (
    TOGGLE_PAYMENT_MONOBANK,
    TOGGLE_PAYMENT_NOVAPAY,
    TOGGLE_PAYMENT_LIQPAY,
    TOGGLE_PAYMENT_COD,
    TOGGLE_DELIVERY_PICKUP,
    TOGGLE_DELIVERY_NOVA_POSHTA,
    TOGGLE_DELIVERY_COURIER,
    TOGGLE_SUPPLIER_UTR,
    TOGGLE_SUPPLIER_GPL,
    TOGGLE_VCHASNO_KASA,
    TOGGLE_SEO,
    TOGGLE_EMAIL,
    TOGGLE_TELEGRAM_MASTER,
    TOGGLE_TELEGRAM_OPS,
    TOGGLE_TELEGRAM_SUPPORT,
    TOGGLE_TELEGRAM_SYSTEM,
)


class IntegrationCenterPatchSerializer(serializers.Serializer):
    ACTION_TOGGLE = "toggle"
    ACTION_TRANSLATOR = "translator"
    ACTION_AUTODB_REMOTE = "autodb_remote"
    ACTION_CHOICES = (
        (ACTION_TOGGLE, ACTION_TOGGLE),
        (ACTION_TRANSLATOR, ACTION_TRANSLATOR),
        (ACTION_AUTODB_REMOTE, ACTION_AUTODB_REMOTE),
    )

    action = serializers.ChoiceField(choices=ACTION_CHOICES, default=ACTION_TOGGLE)
    key = serializers.ChoiceField(choices=SUPPORTED_TOGGLE_KEYS, required=False)
    enabled = serializers.BooleanField(required=False)
    provider = serializers.ChoiceField(
        choices=AutoDbTranslationSettings.PROVIDER_CHOICES,
        required=False,
    )
    google_api_key = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    remote_host = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    remote_port = serializers.IntegerField(required=False, min_value=1, max_value=65535)
    remote_database = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    remote_user = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    remote_password = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    image_base_url = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    def validate(self, attrs: dict) -> dict:
        action = str(attrs.get("action") or self.ACTION_TOGGLE).strip().lower()
        if action == self.ACTION_TOGGLE:
            if "key" not in attrs or "enabled" not in attrs:
                raise serializers.ValidationError({"detail": "Toggle action requires `key` and `enabled`."})
            return attrs
        if action == self.ACTION_TRANSLATOR:
            if "provider" not in attrs and "google_api_key" not in attrs:
                raise serializers.ValidationError({"detail": "Translator action requires `provider` or `google_api_key`."})
            return attrs
        if action == self.ACTION_AUTODB_REMOTE:
            mutable_keys = {"remote_host", "remote_port", "remote_database", "remote_user", "remote_password", "image_base_url"}
            if not (mutable_keys & set(attrs.keys())):
                raise serializers.ValidationError(
                    {"detail": "Auto_DB remote action requires one of: remote_host, remote_port, remote_database, remote_user, remote_password, image_base_url."}
                )
            if "image_base_url" in attrs:
                image_base_url = str(attrs["image_base_url"] or "").strip()
                if image_base_url and not _is_valid_http_url(image_base_url):
                    raise serializers.ValidationError({"image_base_url": "Image Base URL must start with http:// or https://"})
            return attrs
        raise serializers.ValidationError({"detail": "Unsupported action."})


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(parsed.netloc)


def _build_integration_center_state() -> dict[str, bool]:
    checkout = get_checkout_method_settings()
    monobank = get_monobank_settings()
    novapay = get_novapay_settings()
    liqpay = get_liqpay_settings()
    email = get_email_delivery_settings()
    seo = get_seo_site_settings()
    telegram = get_telegram_settings()
    gpl = get_supplier_integration_by_code(source_code="gpl")
    utr = get_supplier_integration_by_code(source_code="utr")
    vchasno_enabled = has_vchasno_kasa_settings_table() and bool(get_vchasno_kasa_settings().is_enabled)

    return {
        TOGGLE_PAYMENT_MONOBANK: bool(monobank.is_enabled),
        TOGGLE_PAYMENT_NOVAPAY: bool(novapay.is_enabled),
        TOGGLE_PAYMENT_LIQPAY: bool(liqpay.is_enabled),
        TOGGLE_PAYMENT_COD: bool(checkout.cash_on_delivery_enabled),
        TOGGLE_DELIVERY_PICKUP: bool(checkout.pickup_enabled),
        TOGGLE_DELIVERY_NOVA_POSHTA: bool(checkout.nova_poshta_enabled),
        TOGGLE_DELIVERY_COURIER: bool(checkout.courier_enabled),
        TOGGLE_SUPPLIER_UTR: bool(utr.is_enabled),
        TOGGLE_SUPPLIER_GPL: bool(gpl.is_enabled),
        TOGGLE_VCHASNO_KASA: bool(vchasno_enabled),
        TOGGLE_SEO: bool(seo.is_enabled),
        TOGGLE_EMAIL: bool(email.is_enabled),
        TOGGLE_TELEGRAM_MASTER: bool(telegram.is_enabled),
        TOGGLE_TELEGRAM_OPS: bool(telegram.ops_enabled),
        TOGGLE_TELEGRAM_SUPPORT: bool(telegram.support_enabled),
        TOGGLE_TELEGRAM_SYSTEM: bool(telegram.system_enabled),
    }


def _mask_secret_value(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}{'*' * (len(clean) - 8)}{clean[-4:]}"


def _build_translator_state() -> dict[str, str | bool]:
    fallback_provider = str(
        getattr(django_settings, "AUTODB_OFFLINE_TRANSLATE_PROVIDER", AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE)
        or AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE
    ).strip().lower()
    if fallback_provider not in {AutoDbTranslationSettings.PROVIDER_GOOGLE, AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE}:
        fallback_provider = AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE
    fallback_google_key = str(getattr(django_settings, "AUTODB_GOOGLE_TRANSLATE_API_KEY", "") or "").strip()

    provider = fallback_provider
    google_key = fallback_google_key
    if has_autodb_translation_settings_table():
        settings = get_autodb_translation_settings()
        db_provider = str(settings.provider or "").strip().lower()
        if db_provider in {AutoDbTranslationSettings.PROVIDER_GOOGLE, AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE}:
            provider = db_provider
        db_google_key = str(settings.google_api_key or "").strip()
        if db_google_key:
            google_key = db_google_key

    return {
        "provider": provider,
        "google_api_key_masked": _mask_secret_value(google_key),
        "has_google_api_key": bool(google_key),
    }


def _build_autodb_remote_state() -> dict[str, object]:
    if not has_autodb_remote_settings_table():
        return {
            "has_schema": False,
            "remote_host": "",
            "remote_port": 3306,
            "remote_database": "",
            "remote_user_masked": "",
            "remote_password_masked": "",
            "has_remote_user": False,
            "has_remote_password": False,
            "image_base_url": "",
        }
    settings = get_autodb_remote_settings()
    remote_user = str(settings.remote_user or "").strip()
    remote_password = str(settings.remote_password or "").strip()
    return {
        "has_schema": True,
        "remote_host": str(settings.remote_host or "").strip(),
        "remote_port": int(settings.remote_port or 3306),
        "remote_database": str(settings.remote_database or "").strip(),
        "remote_user": remote_user,
        "remote_password": remote_password,
        "remote_user_masked": _mask_secret_value(remote_user),
        "remote_password_masked": _mask_secret_value(remote_password),
        "has_remote_user": bool(remote_user),
        "has_remote_password": bool(remote_password),
        "image_base_url": str(settings.image_base_url or "").strip(),
    }


def _build_integration_center_payload() -> dict[str, object]:
    return {
        "state": _build_integration_center_state(),
        "translator": _build_translator_state(),
        "autodb_remote": _build_autodb_remote_state(),
    }


class BackofficeIntegrationCenterAPIView(BackofficeAPIView):
    required_capability = "integrations.manage"

    def get(self, request):
        return Response(_build_integration_center_payload(), status=status.HTTP_200_OK)

    @transaction.atomic
    def patch(self, request):
        serializer = IntegrationCenterPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        if action == IntegrationCenterPatchSerializer.ACTION_TOGGLE:
            self._patch_toggle(serializer.validated_data)
        elif action == IntegrationCenterPatchSerializer.ACTION_TRANSLATOR:
            self._patch_translator(serializer.validated_data)
        elif action == IntegrationCenterPatchSerializer.ACTION_AUTODB_REMOTE:
            self._patch_autodb_remote(serializer.validated_data)
        else:
            raise ValidationError({"action": "Unsupported action."})

        return Response(_build_integration_center_payload(), status=status.HTTP_200_OK)

    def _patch_toggle(self, payload: dict[str, object]) -> None:
        key = str(payload["key"])
        enabled = bool(payload["enabled"])
        checkout = get_checkout_method_settings()

        def update_checkout(field: str, value: bool) -> None:
            checkout_serializer = CheckoutMethodSettingsSerializer(checkout, data={field: value}, partial=True)
            checkout_serializer.is_valid(raise_exception=True)
            checkout_serializer.save()

        mutators: dict[str, Callable[[], None]] = {
            TOGGLE_PAYMENT_MONOBANK: lambda: self._update_payment_with_checkout(
                enabled=enabled,
                payment_model=get_monobank_settings(),
                checkout_field="monobank_enabled",
                update_checkout=update_checkout,
            ),
            TOGGLE_PAYMENT_NOVAPAY: lambda: self._update_payment_with_checkout(
                enabled=enabled,
                payment_model=get_novapay_settings(),
                checkout_field="novapay_enabled",
                update_checkout=update_checkout,
            ),
            TOGGLE_PAYMENT_LIQPAY: lambda: self._update_payment_with_checkout(
                enabled=enabled,
                payment_model=get_liqpay_settings(),
                checkout_field="liqpay_enabled",
                update_checkout=update_checkout,
            ),
            TOGGLE_PAYMENT_COD: lambda: update_checkout("cash_on_delivery_enabled", enabled),
            TOGGLE_DELIVERY_PICKUP: lambda: update_checkout("pickup_enabled", enabled),
            TOGGLE_DELIVERY_NOVA_POSHTA: lambda: update_checkout("nova_poshta_enabled", enabled),
            TOGGLE_DELIVERY_COURIER: lambda: update_checkout("courier_enabled", enabled),
            TOGGLE_SUPPLIER_UTR: lambda: self._update_supplier_enabled(source_code="utr", enabled=enabled),
            TOGGLE_SUPPLIER_GPL: lambda: self._update_supplier_enabled(source_code="gpl", enabled=enabled),
            TOGGLE_VCHASNO_KASA: lambda: self._update_vchasno_enabled(enabled=enabled),
            TOGGLE_SEO: lambda: self._update_seo_enabled(enabled=enabled),
            TOGGLE_EMAIL: lambda: self._update_email_enabled(enabled=enabled),
            TOGGLE_TELEGRAM_MASTER: lambda: self._update_telegram_enabled(field="is_enabled", enabled=enabled),
            TOGGLE_TELEGRAM_OPS: lambda: self._update_telegram_enabled(field="ops_enabled", enabled=enabled),
            TOGGLE_TELEGRAM_SUPPORT: lambda: self._update_telegram_enabled(field="support_enabled", enabled=enabled),
            TOGGLE_TELEGRAM_SYSTEM: lambda: self._update_telegram_enabled(field="system_enabled", enabled=enabled),
        }

        mutator = mutators.get(key)
        if mutator is None:
            raise ValidationError({"key": "Unsupported toggle key."})
        mutator()

    @staticmethod
    def _patch_translator(payload: dict[str, object]) -> None:
        if not has_autodb_translation_settings_table():
            raise ValidationError({"detail": "Auto_DB translation settings table is missing. Apply migrations first."})
        settings = get_autodb_translation_settings()
        update_fields: list[str] = []
        if "provider" in payload:
            settings.provider = str(payload["provider"] or "").strip().lower()
            update_fields.append("provider")
        if "google_api_key" in payload:
            settings.google_api_key = str(payload["google_api_key"] or "").strip()
            update_fields.append("google_api_key")
        if update_fields:
            settings.save(update_fields=tuple(dict.fromkeys([*update_fields, "updated_at"])))

    @staticmethod
    def _patch_autodb_remote(payload: dict[str, object]) -> None:
        if not has_autodb_remote_settings_table():
            raise ValidationError({"detail": "Auto_DB remote settings table is missing. Apply migrations first."})
        settings = get_autodb_remote_settings()
        next_host = str(payload.get("remote_host", settings.remote_host) or "").strip()
        next_database = str(payload.get("remote_database", settings.remote_database) or "").strip()
        next_user = str(payload.get("remote_user", settings.remote_user) or "").strip()
        next_image_base_url = str(payload.get("image_base_url", settings.image_base_url) or "").strip()
        if not next_host:
            raise ValidationError({"remote_host": "Host is required."})
        if not next_database:
            raise ValidationError({"remote_database": "Database is required."})
        if not next_user:
            raise ValidationError({"remote_user": "User is required."})
        if next_image_base_url and not _is_valid_http_url(next_image_base_url):
            raise ValidationError({"image_base_url": "Image Base URL must start with http:// or https://"})

        update_fields: list[str] = []
        if "remote_host" in payload:
            settings.remote_host = next_host
            update_fields.append("remote_host")
        if "remote_port" in payload:
            settings.remote_port = max(int(payload["remote_port"] or 3306), 1)
            update_fields.append("remote_port")
        if "remote_database" in payload:
            settings.remote_database = next_database
            update_fields.append("remote_database")
        if "remote_user" in payload:
            settings.remote_user = next_user
            update_fields.append("remote_user")
        if "remote_password" in payload:
            settings.remote_password = str(payload["remote_password"] or "").strip()
            update_fields.append("remote_password")
        if "image_base_url" in payload:
            settings.image_base_url = next_image_base_url
            update_fields.append("image_base_url")
        if update_fields:
            settings.save(update_fields=tuple(dict.fromkeys([*update_fields, "updated_at"])))


    @staticmethod
    def _update_payment_with_checkout(*, enabled: bool, payment_model, checkout_field: str, update_checkout: Callable[[str, bool], None]) -> None:
        payment_model.is_enabled = enabled
        payment_model.save(update_fields=("is_enabled", "updated_at"))
        update_checkout(checkout_field, enabled)

    @staticmethod
    def _update_supplier_enabled(*, source_code: str, enabled: bool) -> None:
        integration = get_supplier_integration_by_code(source_code=source_code)
        integration.is_enabled = enabled
        integration.save(update_fields=("is_enabled", "updated_at"))

    @staticmethod
    def _update_vchasno_enabled(*, enabled: bool) -> None:
        if not has_vchasno_kasa_settings_table():
            raise ValidationError({"detail": "Vchasno.Kasa schema is not ready."})
        settings = get_vchasno_kasa_settings()
        settings.is_enabled = enabled
        settings.save(update_fields=("is_enabled", "updated_at"))

    @staticmethod
    def _update_seo_enabled(*, enabled: bool) -> None:
        settings = get_seo_site_settings()
        settings.is_enabled = enabled
        settings.save(update_fields=("is_enabled", "updated_at"))

    @staticmethod
    def _update_email_enabled(*, enabled: bool) -> None:
        settings = get_email_delivery_settings()
        settings.is_enabled = enabled
        settings.save(update_fields=("is_enabled", "updated_at"))

    @staticmethod
    def _update_telegram_enabled(*, field: str, enabled: bool) -> None:
        settings = get_telegram_settings()
        setattr(settings, field, bool(enabled))
        settings.save(update_fields=(field, "updated_at"))


class BackofficeAutoDbRemoteConnectionTestAPIView(BackofficeAPIView):
    required_capability = "integrations.manage"

    def post(self, request):
        if not has_autodb_remote_settings_table():
            raise ValidationError({"detail": "Auto_DB remote settings table is missing. Apply migrations first."})

        settings = get_autodb_remote_settings()
        host = str(settings.remote_host or "").strip()
        database = str(settings.remote_database or "").strip()
        user = str(settings.remote_user or "").strip()
        password = str(settings.remote_password or "").strip()
        image_base_url = str(settings.image_base_url or "").strip()
        port = int(settings.remote_port or 0)

        if not host:
            raise ValidationError({"remote_host": "Host is required."})
        if not database:
            raise ValidationError({"remote_database": "Database is required."})
        if not user:
            raise ValidationError({"remote_user": "User is required."})
        if not password:
            raise ValidationError({"remote_password": "Password is required."})
        if port < 1 or port > 65535:
            raise ValidationError({"remote_port": "Port must be in range 1..65535."})
        if image_base_url and not _is_valid_http_url(image_base_url):
            raise ValidationError({"image_base_url": "Image Base URL must start with http:// or https://"})

        try:
            ok = AutoDbProRemoteClient.from_settings().check_connection()
        except (AutoDbProRemoteClientError, AutoDbRemoteConfigError) as exc:
            return Response({"ok": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not ok:
            return Response({"ok": False, "message": "Auto_DB remote connection failed."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, "message": "Auto_DB remote connection successful."}, status=status.HTTP_200_OK)
