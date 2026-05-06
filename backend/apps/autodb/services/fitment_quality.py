from __future__ import annotations

from dataclasses import dataclass
import re

from django.utils import timezone

from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.compatibility.models import ProductFitment


@dataclass(frozen=True)
class ProductFitmentQualityResult:
    suspicious_link: bool
    suspicious_reason: str
    product_tokens: tuple[str, ...]
    reference_tokens: tuple[str, ...]


@dataclass(frozen=True)
class PersistedAutoDbLinkQualityResult:
    status: str
    reason: str
    excluded_from_public_filtering: bool
    manually_confirmed: bool


class ProductFitmentQualityService:
    _token_re = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9]{2,}")

    def __init__(self, *, translator: ProductNameTranslationService | None = None):
        self.translator = translator or ProductNameTranslationService()

    def evaluate(
        self,
        *,
        product: Product,
        autodb_article_title: str,
        autodb_prd_title: str,
    ) -> ProductFitmentQualityResult:
        product_titles = [
            str(getattr(product, "name_uk", "") or ""),
            str(getattr(product, "name_ru", "") or ""),
            str(getattr(product, "name_en", "") or ""),
            str(getattr(product, "name", "") or ""),
            str(getattr(getattr(product, "category", None), "name_uk", "") or ""),
            str(getattr(getattr(product, "category", None), "name_ru", "") or ""),
            str(getattr(getattr(product, "category", None), "name_en", "") or ""),
            str(getattr(getattr(product, "category", None), "name", "") or ""),
        ]
        product_token_sets = [self._tokenize(item) for item in product_titles if item]
        product_token_sets = [tokens for tokens in product_token_sets if len(tokens) >= 2]

        reference_base = autodb_article_title or autodb_prd_title
        if not product_token_sets or not reference_base:
            return ProductFitmentQualityResult(
                suspicious_link=False,
                suspicious_reason="",
                product_tokens=(),
                reference_tokens=(),
            )

        translated = self.translator.translate_product_name(source_text=reference_base)
        reference_titles = [autodb_article_title, autodb_prd_title, translated.uk, translated.ru, translated.en]
        reference_token_sets = [self._tokenize(item) for item in reference_titles if item]
        reference_token_sets = [tokens for tokens in reference_token_sets if len(tokens) >= 2]
        if not reference_token_sets:
            return ProductFitmentQualityResult(
                suspicious_link=False,
                suspicious_reason="",
                product_tokens=(),
                reference_tokens=(),
            )

        for product_tokens in product_token_sets:
            for reference_tokens in reference_token_sets:
                if product_tokens.intersection(reference_tokens):
                    return ProductFitmentQualityResult(
                        suspicious_link=False,
                        suspicious_reason="",
                        product_tokens=tuple(sorted(product_tokens)),
                        reference_tokens=tuple(sorted(reference_tokens)),
                    )

        product_preview = " | ".join(item for item in product_titles if item)[:240]
        reference_preview = " | ".join(item for item in reference_titles if item)[:240]
        reason = f"product_name_vs_autodb_conflict product={product_preview} autodb={reference_preview}"
        return ProductFitmentQualityResult(
            suspicious_link=True,
            suspicious_reason=reason,
            product_tokens=tuple(sorted(product_token_sets[0])),
            reference_tokens=tuple(sorted(reference_token_sets[0])),
        )

    def _tokenize(self, value: str) -> set[str]:
        text = str(value or "").lower()
        raw = self._token_re.findall(text)
        return {item for item in raw if len(item) >= 4 and not item.isdigit()}


class AutoDbProductLinkQualityService:
    def resolve_link_identity(self, *, product: Product) -> tuple[str, int | None, str]:
        article_key = str(getattr(product, "autodb_article_key", "") or "").strip()
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if article_key:
            return article_key, supplier_id, article_number

        fitment = (
            ProductFitment.objects.filter(product=product, source=ProductFitment.SOURCE_AUTODB_PRO)
            .exclude(autodb_article_key="")
            .order_by("autodb_article_key", "id")
            .first()
        )
        if fitment is None:
            return "", supplier_id, article_number
        return (
            str(fitment.autodb_article_key or "").strip(),
            self._safe_int(fitment.supplier_id) or supplier_id,
            str(fitment.article_number or "").strip() or article_number,
        )

    def persist_audit_result(
        self,
        *,
        product: Product,
        suspicious_flags: tuple[str, ...],
        suspicious_reason: str,
        evidence: dict,
    ) -> PersistedAutoDbLinkQualityResult:
        article_key, supplier_id, article_number = self.resolve_link_identity(product=product)
        if not article_key:
            return PersistedAutoDbLinkQualityResult(
                status="",
                reason="",
                excluded_from_public_filtering=False,
                manually_confirmed=False,
            )

        status, reason = self._resolve_automatic_status(
            suspicious_flags=suspicious_flags,
            suspicious_reason=suspicious_reason,
        )
        checked_at = timezone.now()
        defaults = {
            "autodb_supplier_id": supplier_id,
            "autodb_article_number": article_number,
            "status": status,
            "reason": reason,
            "evidence": evidence,
            "checked_at": checked_at,
            "manually_confirmed": False,
        }
        record, created = AutoDbProductLinkQuality.objects.get_or_create(
            product=product,
            autodb_article_key=article_key,
            defaults=defaults,
        )
        if not created:
            record.autodb_supplier_id = supplier_id
            record.autodb_article_number = article_number
            record.checked_at = checked_at
            record.evidence = evidence
            if not record.manually_confirmed:
                record.status = status
                record.reason = reason
            record.save(
                update_fields=(
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "checked_at",
                    "evidence",
                    "status",
                    "reason",
                    "updated_at",
                )
            )

        effective_status = str(record.status or "")
        excluded = self._status_excludes_from_public_filtering(effective_status)
        self._sync_fitments(
            product=product,
            article_key=article_key,
            status=effective_status,
            reason=str(record.reason or ""),
            excluded=excluded,
        )
        return PersistedAutoDbLinkQualityResult(
            status=effective_status,
            reason=str(record.reason or ""),
            excluded_from_public_filtering=excluded,
            manually_confirmed=bool(record.manually_confirmed),
        )

    def confirm_manual_status(
        self,
        *,
        product: Product,
        status: str,
        reason: str = "",
        note: str = "",
        evidence: dict | None = None,
    ) -> PersistedAutoDbLinkQualityResult:
        normalized_status = str(status or "").strip()
        valid_statuses = {
            AutoDbProductLinkQuality.STATUS_TRUSTED,
            AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        }
        if normalized_status not in valid_statuses:
            raise ValueError(f"Unsupported manual status: {status}")

        article_key, supplier_id, article_number = self.resolve_link_identity(product=product)
        if not article_key:
            raise ValueError("Product is not linked to an Auto_DB_Pro article key")

        checked_at = timezone.now()
        normalized_reason = str(reason or "").strip()
        normalized_note = str(note or "").strip()
        record, _ = AutoDbProductLinkQuality.objects.update_or_create(
            product=product,
            autodb_article_key=article_key,
            defaults={
                "autodb_supplier_id": supplier_id,
                "autodb_article_number": article_number,
                "status": normalized_status,
                "reason": normalized_reason,
                "checked_at": checked_at,
                "manually_confirmed": True,
                "note": normalized_note,
                "evidence": evidence
                or {
                    "source": "manual_confirmation",
                    "status": normalized_status,
                    "reason": normalized_reason,
                    "note": normalized_note,
                    "checked_at": checked_at.isoformat(),
                },
            },
        )
        excluded = self._status_excludes_from_public_filtering(normalized_status)
        self._sync_fitments(
            product=product,
            article_key=article_key,
            status=normalized_status,
            reason=normalized_reason,
            excluded=excluded,
        )
        return PersistedAutoDbLinkQualityResult(
            status=str(record.status or ""),
            reason=str(record.reason or ""),
            excluded_from_public_filtering=excluded,
            manually_confirmed=bool(record.manually_confirmed),
        )

    def can_use_for_public_filtering(self, *, product: Product) -> bool:
        article_key, _, _ = self.resolve_link_identity(product=product)
        if not article_key:
            return False

        active_fitments = ProductFitment.objects.filter(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_article_key=article_key,
            is_stale=False,
        )
        if not active_fitments.exists():
            return False
        if ProductFitment.objects.filter(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_article_key=article_key,
            is_stale=True,
        ).exists():
            return False
        if active_fitments.filter(excluded_from_public_filtering=True).exists():
            return False
        if active_fitments.exclude(quality_status="").exclude(
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED
        ).exists():
            return False

        quality = (
            AutoDbProductLinkQuality.objects.filter(product=product, autodb_article_key=article_key)
            .order_by("-checked_at", "-updated_at")
            .first()
        )
        if quality is None:
            return True
        if quality.manually_confirmed:
            return str(quality.status or "") == AutoDbProductLinkQuality.STATUS_TRUSTED
        return str(quality.status or "") == AutoDbProductLinkQuality.STATUS_TRUSTED

    def _resolve_automatic_status(
        self,
        *,
        suspicious_flags: tuple[str, ...],
        suspicious_reason: str,
    ) -> tuple[str, str]:
        if "suspicious_link" in suspicious_flags:
            return AutoDbProductLinkQuality.STATUS_SUSPICIOUS, str(suspicious_reason or "").strip()
        return AutoDbProductLinkQuality.STATUS_TRUSTED, ""

    def _sync_fitments(
        self,
        *,
        product: Product,
        article_key: str,
        status: str,
        reason: str,
        excluded: bool,
    ) -> None:
        ProductFitment.objects.filter(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_article_key=article_key,
        ).update(
            quality_status=status,
            quality_reason=reason,
            excluded_from_public_filtering=excluded,
        )

    def _status_excludes_from_public_filtering(self, status: str) -> bool:
        return status in {
            AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
            AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        }

    def _safe_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def can_use_autodb_fitments_for_public_filtering(*, product: Product) -> bool:
    return AutoDbProductLinkQualityService().can_use_for_public_filtering(product=product)
