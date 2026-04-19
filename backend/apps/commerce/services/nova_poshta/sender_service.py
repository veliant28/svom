from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.commerce.models import NovaPoshtaSenderProfile

from .client import NovaPoshtaApiClient
from .errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError
from .normalizers import first_data_item
from .payment_rules import resolve_effective_sender_type, validate_sender_capabilities


class NovaPoshtaSenderProfileService:
    def list_profiles(self):
        return NovaPoshtaSenderProfile.objects.order_by("-is_default", "name")

    def get_profile(self, *, profile_id):
        return NovaPoshtaSenderProfile.objects.get(id=profile_id)

    @transaction.atomic
    def ensure_default_uniqueness(self, *, profile: NovaPoshtaSenderProfile) -> None:
        if not profile.is_default:
            return
        NovaPoshtaSenderProfile.objects.exclude(id=profile.id).filter(is_default=True).update(is_default=False)

    @transaction.atomic
    def set_default(self, *, profile: NovaPoshtaSenderProfile) -> NovaPoshtaSenderProfile:
        profile.is_default = True
        profile.save(update_fields=("is_default", "updated_at"))
        NovaPoshtaSenderProfile.objects.exclude(id=profile.id).filter(is_default=True).update(is_default=False)
        return profile

    def get_default_active_profile(self) -> NovaPoshtaSenderProfile:
        profile = (
            NovaPoshtaSenderProfile.objects.filter(is_active=True, is_default=True)
            .order_by("name")
            .first()
        )
        if profile:
            return profile

        profile = NovaPoshtaSenderProfile.objects.filter(is_active=True).order_by("name").first()
        if not profile:
            raise NovaPoshtaBusinessRuleError("Не найден активный профиль отправителя Новой Почты.")
        return profile

    def validate_profile(self, *, profile: NovaPoshtaSenderProfile) -> dict:
        self._validate_required_fields(profile)

        client = NovaPoshtaApiClient(api_token=profile.api_token)
        normalized_counterparty_ref = str(profile.counterparty_ref or "").strip()
        healed_contact_ref = str(profile.contact_ref or "").strip()
        try:
            response = client.get_counterparty_options(counterparty_ref=normalized_counterparty_ref)
        except NovaPoshtaIntegrationError as exc:
            healed_counterparty_ref = self._resolve_counterparty_ref(client=client, profile=profile)
            if not healed_counterparty_ref or healed_counterparty_ref == normalized_counterparty_ref:
                raise exc
            normalized_counterparty_ref = healed_counterparty_ref
            healed_contact_ref = self._resolve_contact_ref(
                client=client,
                counterparty_ref=normalized_counterparty_ref,
                fallback_contact_ref=healed_contact_ref,
            )
            response = client.get_counterparty_options(counterparty_ref=normalized_counterparty_ref)
        options = first_data_item(response.payload)
        effective_sender_type = resolve_effective_sender_type(
            sender_type=profile.sender_type,
            hints=_collect_sender_type_hints(profile),
        )

        validate_sender_capabilities(sender_type=effective_sender_type, options=options)

        profile.counterparty_ref = normalized_counterparty_ref
        profile.contact_ref = healed_contact_ref
        profile.last_validated_at = timezone.now()
        profile.last_validation_ok = True
        profile.last_validation_message = "Профиль валиден."
        profile.last_validation_payload = response.payload
        profile.save(
            update_fields=(
                "counterparty_ref",
                "contact_ref",
                "last_validated_at",
                "last_validation_ok",
                "last_validation_message",
                "last_validation_payload",
                "updated_at",
            )
        )

        return {
            "ok": True,
            "message": profile.last_validation_message,
            "options": options,
        }

    def mark_validation_failed(self, *, profile: NovaPoshtaSenderProfile, message: str, payload: dict | None = None) -> None:
        profile.last_validated_at = timezone.now()
        profile.last_validation_ok = False
        profile.last_validation_message = message[:500]
        profile.last_validation_payload = payload or {}
        profile.save(
            update_fields=(
                "last_validated_at",
                "last_validation_ok",
                "last_validation_message",
                "last_validation_payload",
                "updated_at",
            )
        )

    def _validate_required_fields(self, profile: NovaPoshtaSenderProfile) -> None:
        required: list[tuple[str, str]] = [
            (profile.api_token, "api token"),
            (profile.counterparty_ref, "counterparty ref"),
            (profile.contact_ref, "contact ref"),
            (profile.address_ref, "address ref"),
            (profile.city_ref, "city ref"),
            (profile.phone, "phone"),
        ]
        missing = [name for value, name in required if not str(value or "").strip()]
        if missing:
            raise NovaPoshtaBusinessRuleError(
                f"Профиль отправителя заполнен не полностью. Отсутствуют поля: {', '.join(missing)}.",
            )

        if profile.sender_type in {NovaPoshtaSenderProfile.TYPE_FOP, NovaPoshtaSenderProfile.TYPE_BUSINESS}:
            if not profile.contact_name.strip():
                raise NovaPoshtaBusinessRuleError(
                    "Для отправителя типа ФОП/Организация нужно заполнить контактное лицо.",
                )

    def _resolve_counterparty_ref(self, *, client: NovaPoshtaApiClient, profile: NovaPoshtaSenderProfile) -> str:
        raw_meta = profile.raw_meta if isinstance(profile.raw_meta, dict) else {}
        candidates: list[str] = []
        for value in (
            raw_meta.get("counterparty_label"),
            profile.contact_name,
            profile.name,
        ):
            normalized = str(value or "").strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        if not candidates:
            return ""

        current_counterparty_ref = str(profile.counterparty_ref or "").strip()
        for query in candidates:
            try:
                lookup = client.get_counterparties(counterparty_property="Sender", query=query)
            except NovaPoshtaIntegrationError:
                continue

            data = lookup.payload.get("data")
            if not isinstance(data, list):
                continue

            for row in data:
                if not isinstance(row, dict):
                    continue
                ref = str(row.get("Ref") or "").strip()
                if not ref:
                    continue
                row_counterparty = str(row.get("Counterparty") or "").strip()
                row_description = str(row.get("Description") or "").strip()
                if row_counterparty and row_counterparty == current_counterparty_ref:
                    return ref
                if row_description and row_description.casefold() == query.casefold():
                    return ref

        return ""

    def _resolve_contact_ref(
        self,
        *,
        client: NovaPoshtaApiClient,
        counterparty_ref: str,
        fallback_contact_ref: str,
    ) -> str:
        normalized_fallback = str(fallback_contact_ref or "").strip()
        try:
            contacts_response = client.get_counterparty_contact_persons(counterparty_ref=counterparty_ref)
        except NovaPoshtaIntegrationError:
            return normalized_fallback

        data = contacts_response.payload.get("data")
        if not isinstance(data, list) or not data:
            return normalized_fallback

        first_row = data[0] if isinstance(data[0], dict) else {}
        resolved_ref = str(first_row.get("Ref") or "").strip()
        return resolved_ref or normalized_fallback


def _collect_sender_type_hints(profile: NovaPoshtaSenderProfile) -> tuple[str, ...]:
    raw_meta = profile.raw_meta if isinstance(profile.raw_meta, dict) else {}
    candidates = (
        str(raw_meta.get("inferred_sender_type") or ""),
        str(raw_meta.get("counterparty_type") or ""),
        str(raw_meta.get("ownership_form_description") or ""),
        str(raw_meta.get("counterparty_label") or ""),
        str(profile.organization_name or ""),
        str(profile.edrpou or ""),
        str(profile.name or ""),
        str(profile.contact_name or ""),
    )
    return tuple(item.strip() for item in candidates if str(item or "").strip())
