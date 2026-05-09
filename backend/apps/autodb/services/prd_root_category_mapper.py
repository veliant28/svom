from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from apps.catalog.models import Category
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS, manual_root_spec_by_slug


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


@dataclass(frozen=True)
class RootMappingResult:
    status: str
    root_slug: str
    root_name: str
    confidence: float
    reason: str


class AutoDbPrdRootCategoryMapper:
    STATUS_MAPPED = "mapped"
    STATUS_NEEDS_ROOT_CATEGORY_MAPPING = "needs_root_category_mapping"

    _RULES: tuple[tuple[str, tuple[str, ...], float], ...] = (
        (
            "dvigatel-i-vykhlop",
            (
                "фильтр",
                "фільтр",
                "filter",
                "ремень",
                "ролик",
                "грм",
                "service",
                "то ",
            ),
            0.9,
        ),
        (
            "avtohimiia-i-aksessuary",
            (
                "автохим",
                "автохім",
                "масло",
                "oil",
                "очист",
                "присад",
                "эмал",
                "краск",
                "смаз",
                "аксесс",
                "аксесу",
                "инструмент",
                "інструмент",
                "крепеж",
                "кріпл",
            ),
            0.84,
        ),
        (
            "tormoznaia-sistema",
            (
                "тормоз",
                "гальм",
                "brake",
                "колодк",
                "суппорт",
                "диск торм",
                "ремкомплект суппорт",
            ),
            0.95,
        ),
        (
            "okhlazhdenie-i-otoplenie",
            (
                "охлажд",
                "охолод",
                "термостат",
                "радиатор",
                "радіатор",
                "помпа",
                "кондиц",
                "отопл",
                "печк",
                "cool",
                "heat",
                "radiator",
            ),
            0.9,
        ),
        (
            "dvigatel-i-vykhlop",
            (
                "двиг",
                "двигун",
                "мотор",
                "exhaust",
                "выхлоп",
                "вихлоп",
                "глуш",
                "сальник",
                "топлив",
                "паливн",
                "инжектор",
            ),
            0.88,
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
                "ступиц",
                "рулев",
                "кермов",
                "тяга",
                "стойк",
            ),
            0.9,
        ),
        (
            "stseplenie-i-transmissiia",
            (
                "сцеплен",
                "зчеплен",
                "трансм",
                "кпп",
                "gear",
                "шрус",
                "привод",
                "кардан",
                "коробка передач",
            ),
            0.86,
        ),
        (
            "elektrika-i-osveshchenie",
            (
                "датчик",
                "ламп",
                "фара",
                "освещ",
                "освіт",
                "генератор",
                "стартер",
                "катуш",
                "свеча зажиган",
                "свеча накал",
                "свіч",
                "запал",
                "ignition",
                "spark plug",
                "glow plug",
                "electr",
                "реле",
                "провод",
                "блок управл",
                "ignition coil",
            ),
            0.86,
        ),
        (
            "detali-kuzova",
            (
                "кузов",
                "салон",
                "зеркал",
                "дзеркал",
                "бампер",
                "капот",
                "двер",
                "стекл",
                "скло",
                "крыл",
                "фар",
                "body",
                "дверн",
            ),
            0.84,
        ),
        (
            "kolesa-i-shiny",
            (
                "колес",
                "коліс",
                "шин",
                "шини",
                "tyre",
                "tire",
                "rim",
                "диск",
            ),
            0.9,
        ),
        (
            "okhlazhdenie-i-otoplenie",
            (
                "климат",
                "клімат",
                "комфорт",
                "безопас",
                "безпек",
                "кондиц",
                "отопл",
                "вентиляц",
                "climate",
                "comfort",
                "safety",
            ),
            0.78,
        ),
    )

    _SERVICE_IGNITION_KEYWORDS = ("свеча зажиган", "свеча накал", "свіч", "запал", "spark plug", "glow plug")
    _ELECTRIC_IGNITION_KEYWORDS = (
        "катуш",
        "модул",
        "провод",
        "реле",
        "датчик",
        "блок управл",
        "ignition coil",
        "cable",
    )

    def resolve(
        self,
        *,
        prd_description: str,
        prd_normalized_description: str,
        prd_assembly_group_description: str,
        prd_usage_description: str = "",
        product_display_name: str,
        autodb_article_title: str,
    ) -> RootMappingResult:
        haystack = self._build_haystack(
            [
                prd_description,
                prd_normalized_description,
                prd_assembly_group_description,
                prd_usage_description,
                product_display_name,
                autodb_article_title,
            ]
        )
        if not haystack:
            return RootMappingResult(
                status=self.STATUS_NEEDS_ROOT_CATEGORY_MAPPING,
                root_slug="",
                root_name="",
                confidence=0.0,
                reason="empty_text",
            )

        group_text = self._build_haystack([prd_assembly_group_description])
        if "система зажигания" in group_text or "накаливан" in group_text:
            if any(token in haystack for token in self._ELECTRIC_IGNITION_KEYWORDS):
                return self._mapped(root_slug="elektrika-i-osveshchenie", confidence=0.91, reason="ignition_context:electrics")
            if any(token in haystack for token in self._SERVICE_IGNITION_KEYWORDS):
                return self._mapped(root_slug="elektrika-i-osveshchenie", confidence=0.93, reason="ignition_context:service_parts")
            return RootMappingResult(
                status=self.STATUS_NEEDS_ROOT_CATEGORY_MAPPING,
                root_slug="",
                root_name="",
                confidence=0.0,
                reason="ignition_context:unclear",
            )
        if "комплектующ" in group_text:
            if any(token in haystack for token in self._SERVICE_IGNITION_KEYWORDS):
                return self._mapped(root_slug="elektrika-i-osveshchenie", confidence=0.9, reason="components_context:service_parts")
            if any(token in haystack for token in ("инструмент", "аксесс", "аксесу", "крепеж", "кріпл", "универсал", "набор")):
                return self._mapped(root_slug="avtohimiia-i-aksessuary", confidence=0.8, reason="components_context:accessory")

        for root_slug, keywords, confidence in self._RULES:
            for keyword in keywords:
                if keyword in haystack:
                    return self._mapped(root_slug=root_slug, confidence=confidence, reason=f"keyword:{keyword}")

        return RootMappingResult(
            status=self.STATUS_NEEDS_ROOT_CATEGORY_MAPPING,
            root_slug="",
            root_name="",
            confidence=0.0,
            reason="no_rule_match",
        )

    def _mapped(self, *, root_slug: str, confidence: float, reason: str) -> RootMappingResult:
        root_name = manual_root_spec_by_slug()[root_slug].name
        return RootMappingResult(
            status=self.STATUS_MAPPED,
            root_slug=root_slug,
            root_name=root_name,
            confidence=confidence,
            reason=reason,
        )

    def resolve_root_category(self, *, root_slug: str) -> Category | None:
        slug = str(root_slug or "").strip()
        if not slug:
            return None
        return Category.objects.filter(parent__isnull=True, slug=slug, source=Category.SOURCE_MANUAL).first()

    @staticmethod
    def expected_root_names() -> tuple[str, ...]:
        return tuple(item.name for item in MANUAL_ROOT_CATEGORY_SPECS)

    def _build_haystack(self, parts: Iterable[str]) -> str:
        joined = " ".join(str(part or "") for part in parts)
        normalized = _normalize_text(joined)
        # Keep Cyrillic/Latin words with spaces for cheap contains matching.
        normalized = re.sub(r"[^0-9a-zа-яіїєґ\s-]+", " ", normalized, flags=re.IGNORECASE)
        return " ".join(normalized.split())
