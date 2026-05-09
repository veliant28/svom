from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _first_nonempty(values: Iterable[str]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


@dataclass(frozen=True)
class SupplierCategoryFallbackInput:
    product_name: str
    supplier_product_name: str
    raw_category: str
    raw_group: str
    raw_name: str
    raw_description: str
    raw_article_td: str
    raw_code: str
    display_brand: str


@dataclass(frozen=True)
class SupplierCategoryFallbackDecision:
    status: str
    proposed_root_slug: str
    proposed_root_name: str
    proposed_child_name: str
    confidence: float
    reason: str


class SupplierCategoryToSiteRootMapper:
    STATUS_MAPPED_ROOT_ONLY = "mapped_root_only"
    STATUS_MAPPED_CHILD_CATEGORY = "mapped_child_category"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_SKIPPED_UNCLEAR = "skipped_unclear"
    STATUS_NON_AUTO_SUPPLIER_ONLY = "non_auto_supplier_only"

    _ROOT_LABEL_BY_SLUG = {item.slug: item.name for item in MANUAL_ROOT_CATEGORY_SPECS}

    _ROOT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "avtohimiia-i-aksessuary",
            (
                "автохим",
                "автохім",
                "масло",
                "oil",
                "емал",
                "эмал",
                "краск",
                "фарб",
                "аерозол",
                "аэрозол",
                "очист",
                "присад",
                "смаз",
                "полир",
                "гермет",
                "клей",
                "аксесс",
                "аксесу",
                "инструмент",
                "інструмент",
                "щетк",
                "щітк",
            ),
        ),
        (
            "dvigatel-i-vykhlop",
            (
                "фильтр",
                "фільтр",
                "ремень",
                "ремін",
                "ролик",
                "сервис",
                "сервіс",
            ),
        ),
        (
            "tormoznaia-sistema",
            (
                "тормоз",
                "гальм",
                "колодк",
                "диск торм",
                "суппорт",
            ),
        ),
        (
            "dvigatel-i-vykhlop",
            (
                "двиг",
                "двигун",
                "мотор",
                "выхлоп",
                "вихлоп",
                "глуш",
                "топлив",
                "палив",
                "насос",
                "проклад",
            ),
        ),
        (
            "podveska-i-rulevoe",
            (
                "амортиз",
                "підвіс",
                "подвес",
                "рычаг",
                "сайлент",
                "шарнир",
                "рулев",
                "кермов",
                "тяга",
                "стойк",
            ),
        ),
        (
            "stseplenie-i-transmissiia",
            (
                "сцеплен",
                "зчеплен",
                "трансм",
                "кпп",
                "шрус",
                "привод",
            ),
        ),
        (
            "elektrika-i-osveshchenie",
            (
                "аккумулятор",
                "акумулятор",
                "свеч",
                "свіч",
                "ламп",
                "фара",
                "датчик",
                "генератор",
                "стартер",
                "реле",
                "катуш",
                "провод",
            ),
        ),
        (
            "detali-kuzova",
            (
                "кузов",
                "салон",
                "зеркал",
                "дзеркал",
                "бампер",
                "двер",
                "стекл",
                "скло",
                "замок",
                "коврик",
                "багаж",
                "щетка стеклоочист",
                "щітка склоочис",
            ),
        ),
        (
            "kolesa-i-shiny",
            (
                "шина",
                "шини",
                "колес",
                "коліс",
                "диск колес",
                "болт колес",
                "секретк",
            ),
        ),
        (
            "okhlazhdenie-i-otoplenie",
            (
                "кондиц",
                "отопл",
                "опален",
                "вентиляц",
                "климат",
                "клімат",
                "охлажд",
                "охолод",
                "безопас",
                "безпек",
                "airbag",
                "ремень безопас",
            ),
        ),
    )

    _PAINT_TOKENS = (
        "емал",
        "эмал",
        "фарб",
        "краск",
        "аерозол",
        "аэрозол",
        "лак",
        "грунт",
    )

    _NON_AUTO_HINT_BRANDS = {
        "CS SYSTEM",
        "MITKA",
        "VIRA",
        "ORGANIC PRINK",
        "MR.BUILD",
    }

    def map(self, payload: SupplierCategoryFallbackInput) -> SupplierCategoryFallbackDecision:
        text = self._build_haystack(payload)
        brand = str(payload.display_brand or "").strip().upper()

        if brand == "K2":
            child = self._suggest_child("avtohimiia-i-aksessuary", text=text)
            status = self.STATUS_MAPPED_CHILD_CATEGORY if child else self.STATUS_MAPPED_ROOT_ONLY
            return self._decision(
                status=status,
                root_slug="avtohimiia-i-aksessuary",
                child=child,
                confidence=0.96,
                reason="brand:k2",
            )

        if brand in {"MITKA", "CS SYSTEM"} and any(token in text for token in self._PAINT_TOKENS):
            child = self._suggest_child("avtohimiia-i-aksessuary", text=text)
            status = self.STATUS_MAPPED_CHILD_CATEGORY if child else self.STATUS_MAPPED_ROOT_ONLY
            return self._decision(
                status=status,
                root_slug="avtohimiia-i-aksessuary",
                child=child,
                confidence=0.98,
                reason=f"brand_paint:{brand.lower()}",
            )

        scores: dict[str, int] = {}
        reasons: dict[str, str] = {}
        for root_slug, keywords in self._ROOT_RULES:
            hits = 0
            sample_keyword = ""
            for keyword in keywords:
                if keyword in text:
                    hits += 1
                    if not sample_keyword:
                        sample_keyword = keyword
            if hits:
                scores[root_slug] = hits
                reasons[root_slug] = sample_keyword

        if not scores:
            if brand in self._NON_AUTO_HINT_BRANDS:
                return SupplierCategoryFallbackDecision(
                    status=self.STATUS_NON_AUTO_SUPPLIER_ONLY,
                    proposed_root_slug="",
                    proposed_root_name="",
                    proposed_child_name="",
                    confidence=0.70,
                    reason=f"non_auto_brand:{brand.lower()}",
                )
            return SupplierCategoryFallbackDecision(
                status=self.STATUS_SKIPPED_UNCLEAR,
                proposed_root_slug="",
                proposed_root_name="",
                proposed_child_name="",
                confidence=0.0,
                reason="no_rule_match",
            )

        ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
        top_slug, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0

        if top_score == second_score and top_score > 0:
            return SupplierCategoryFallbackDecision(
                status=self.STATUS_NEEDS_REVIEW,
                proposed_root_slug=top_slug,
                proposed_root_name=self._ROOT_LABEL_BY_SLUG.get(top_slug, ""),
                proposed_child_name="",
                confidence=0.60,
                reason=f"ambiguous_root:{top_slug}",
            )

        confidence = min(0.99, 0.66 + top_score * 0.08 + max(top_score - second_score, 0) * 0.04)
        child = self._suggest_child(top_slug, text=text)

        if confidence < 0.75:
            return SupplierCategoryFallbackDecision(
                status=self.STATUS_NEEDS_REVIEW,
                proposed_root_slug=top_slug,
                proposed_root_name=self._ROOT_LABEL_BY_SLUG.get(top_slug, ""),
                proposed_child_name=child,
                confidence=round(confidence, 3),
                reason=f"low_confidence:{reasons.get(top_slug, '-')}",
            )

        status = self.STATUS_MAPPED_CHILD_CATEGORY if child else self.STATUS_MAPPED_ROOT_ONLY
        return self._decision(
            status=status,
            root_slug=top_slug,
            child=child,
            confidence=round(confidence, 3),
            reason=f"keyword:{reasons.get(top_slug, '-')}",
        )

    def _decision(
        self,
        *,
        status: str,
        root_slug: str,
        child: str,
        confidence: float,
        reason: str,
    ) -> SupplierCategoryFallbackDecision:
        return SupplierCategoryFallbackDecision(
            status=status,
            proposed_root_slug=root_slug,
            proposed_root_name=self._ROOT_LABEL_BY_SLUG.get(root_slug, ""),
            proposed_child_name=child,
            confidence=round(confidence, 3),
            reason=reason,
        )

    def _build_haystack(self, payload: SupplierCategoryFallbackInput) -> str:
        combined = " ".join(
            [
                payload.product_name,
                payload.supplier_product_name,
                payload.raw_category,
                payload.raw_group,
                payload.raw_name,
                payload.raw_description,
                payload.display_brand,
            ]
        )
        text = _norm(combined)
        return re.sub(r"\s+", " ", text)

    def _suggest_child(self, root_slug: str, *, text: str) -> str:
        if root_slug == "avtohimiia-i-aksessuary":
            if any(token in text for token in self._PAINT_TOKENS):
                return "Автоэмали и краски"
            if "очист" in text:
                return "Очистители кондиционера"
            if "смаз" in text:
                return "Смазка"
            return ""
        if root_slug == "dvigatel-i-vykhlop":
            if "фильтр" in text or "фільтр" in text:
                return "Масляный фильтр"
            if "ремень" in text or "ремін" in text:
                return "Ремень приводной"
            return ""
        if root_slug == "podveska-i-rulevoe" and "амортиз" in text:
            return "Амортизаторы"
        if root_slug == "elektrika-i-osveshchenie" and ("аккумулятор" in text or "акумулятор" in text):
            return "Аккумуляторы"
        return ""


def extract_supplier_payload_fields(raw_payload: dict) -> dict[str, str]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    return {
        "raw_category": _first_nonempty(
            (
                payload.get("Категорія"),
                payload.get("Категория"),
                payload.get("category"),
            )
        ),
        "raw_group": _first_nonempty(
            (
                payload.get("Група ТД"),
                payload.get("Группа ТД"),
                payload.get("group"),
            )
        ),
        "raw_name": _first_nonempty(
            (
                payload.get("Найменування"),
                payload.get("Наименование"),
                payload.get("name"),
                payload.get("title"),
            )
        ),
        "raw_description": _first_nonempty(
            (
                payload.get("Опис"),
                payload.get("Описание"),
                payload.get("description"),
            )
        ),
        "raw_article_td": _first_nonempty(
            (
                payload.get("Артикул ТД"),
                payload.get("article_td"),
                payload.get("manufacturer_article"),
            )
        ),
        "raw_code": _first_nonempty(
            (
                payload.get("Код"),
                payload.get("code"),
                payload.get("cid"),
            )
        ),
    }
