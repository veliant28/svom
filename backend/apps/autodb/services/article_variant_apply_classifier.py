from __future__ import annotations

import re

from apps.catalog.models import AutoDbProductLinkQuality, Product


class ArticleVariantApplyClassifier:
    STATUS_ALREADY_LINKED_SAME_KEY = "already_linked_same_key"
    STATUS_ALREADY_LINKED_CONFLICTING_KEY = "already_linked_conflicting_key"
    STATUS_SAFE_TO_APPLY = "safe_to_apply"
    STATUS_SKIPPED_SUSPICIOUS = "skipped_suspicious"
    STATUS_SKIPPED_SEMANTIC_CONFLICT = "skipped_semantic_conflict"
    STATUS_SKIPPED_LOW_CONFIDENCE = "skipped_low_confidence"
    STATUS_EXACT_NOT_FOUND = "exact_not_found"
    STATUS_NEEDS_MANUAL_REVIEW = "needs_manual_review"
    STATUS_NON_AUTO_IGNORE = "non_auto_ignore"

    SAFE_RECOMMENDATIONS = {"article_in_raw_name", "try_variant", "try_external_sku"}

    _TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9]{4,}", flags=re.UNICODE)

    def classify(
        self,
        *,
        row,
        product: Product | None,
        proposed_key: str,
        min_confidence: float,
        quality_status: str,
        excluded_count: int,
        autodb_title: str,
        autodb_category: str = "",
    ) -> tuple[str, str]:
        if row.recommendation == "exact_not_found" or not proposed_key:
            return self.STATUS_EXACT_NOT_FOUND, row.reason or "exact_not_found"
        if row.recommendation == "non_auto_ignore":
            return self.STATUS_NON_AUTO_IGNORE, row.reason or "non_auto_ignore"
        if product is None:
            return self.STATUS_NEEDS_MANUAL_REVIEW, "no_matched_product_for_apply"

        current_key = str(getattr(product, "autodb_article_key", "") or "").strip()
        if quality_status == AutoDbProductLinkQuality.STATUS_SUSPICIOUS or excluded_count > 0:
            reason = "product_link_quality_is_suspicious"
            if excluded_count > 0:
                reason = f"fitments_excluded_from_public_filtering={excluded_count}"
            return self.STATUS_SKIPPED_SUSPICIOUS, reason
        if current_key and current_key == proposed_key:
            return self.STATUS_ALREADY_LINKED_SAME_KEY, "already_linked_same_key"
        if current_key and current_key != proposed_key:
            return self.STATUS_ALREADY_LINKED_CONFLICTING_KEY, "conflicting_existing_link"
        if row.recommendation not in self.SAFE_RECOMMENDATIONS:
            return self.STATUS_NEEDS_MANUAL_REVIEW, row.reason or row.recommendation or "needs_manual_review"
        if row.confidence < min_confidence:
            return self.STATUS_SKIPPED_LOW_CONFIDENCE, row.reason or "confidence_below_min_threshold"
        if self.has_semantic_conflict(
            raw_name=row.raw_product_name,
            autodb_title=autodb_title,
            autodb_category=autodb_category,
            corrected_article=proposed_key.split(":", 1)[1] if ":" in proposed_key else proposed_key,
        ):
            return self.STATUS_SKIPPED_SEMANTIC_CONFLICT, "semantic_conflict"
        return self.STATUS_SAFE_TO_APPLY, row.reason or "safe_variant_apply_candidate"

    def has_semantic_conflict(
        self,
        *,
        raw_name: str,
        autodb_title: str,
        autodb_category: str = "",
        corrected_article: str,
    ) -> bool:
        raw = str(raw_name or "").strip()
        title_blob = " ".join(item for item in [autodb_title, autodb_category] if item).strip()
        corrected = str(corrected_article or "").strip().upper()
        if not raw or not title_blob:
            return False
        if corrected and corrected in raw.upper():
            return False
        raw_tokens = self._normalized_tokens(raw)
        autodb_tokens = self._normalized_tokens(title_blob)
        if not raw_tokens or not autodb_tokens:
            return False
        return raw_tokens.isdisjoint(autodb_tokens)

    def _normalized_tokens(self, text: str) -> set[str]:
        out: set[str] = set()
        for token in self._TOKEN_RE.findall(str(text or "").lower()):
            value = (
                token.replace("і", "и")
                .replace("ї", "и")
                .replace("є", "е")
                .replace("ґ", "г")
            )
            if value and not value.isdigit():
                out.add(value)
        return out

