from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re
import unicodedata


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[\s_]+", " ", text)
    text = re.sub(r"[^\w\s/>\\|.-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _is_hub_bearing_category(category_text: str) -> bool:
    return _contains_any(
        category_text,
        (
            "підшипник маточ",
            "подшипник ступ",
            "ступич",
            "hub bearing",
            "wheel bearing",
        ),
    )


def _is_brake_pads_category(category_text: str) -> bool:
    return _contains_any(
        category_text,
        (
            "гальмівні колод",
            "тормозн колод",
            "brake pad",
        ),
    )


def _is_cabin_filter_category(category_text: str) -> bool:
    return _contains_any(
        category_text,
        (
            "фільтр салон",
            "фильтр салон",
            "cabin filter",
            "pollen filter",
        ),
    )


_CV_JOINT_TERMS = (
    "шрус",
    "шркш",
    "cv joint",
    "гранат",
    "пыльник",
    "пильник",
    "пильовик",
)
_INJECTOR_TERMS = (
    "форсун",
    "injector",
    "nozzle",
)
_SHOCK_TERMS = (
    "амортиз",
    "стойк",
    "опора амортиз",
    "опори амортиз",
)
_CALIPER_TERMS = (
    "супорт",
    "caliper",
)
_SPRING_OR_REPAIR_TERMS = (
    "пружин",
    "ремкомплект",
    "р/к",
    "р к ",
)
_AIR_FILTER_TERMS = (
    "повітряний фільтр",
    "фильтр воздуш",
    "air filter",
    "фільтр двигун",
    "фильтр двигателя",
    "engine air",
    "intake",
)
_GEARBOX_TERMS = (
    "кпп",
    "коробк",
    "мкпп",
    "акпп",
    "transmission",
    "gearbox",
    "трансмис",
    "bearing kit gearbox",
    "ремкомплект кпп",
)


@dataclass(frozen=True)
class GuardrailHit:
    code: str
    preferred_tokens: tuple[str, ...]
    prefer_auto_status: bool = False
    remap_min_confidence: Decimal | None = None


class CategoryMappingGuardrails:
    def evaluate(
        self,
        *,
        category_name: str,
        category_path: str,
        product_name: str,
    ) -> GuardrailHit | None:
        normalized_name = _normalize_text(category_name)
        normalized_path = _normalize_text(category_path)
        category_text = f"{normalized_name} | {normalized_path}"
        product_text = _normalize_text(product_name)
        if not category_text.strip() or not product_text:
            return None

        if _is_hub_bearing_category(category_text):
            if _contains_any(product_text, _CV_JOINT_TERMS):
                return GuardrailHit(
                    code="hub_bearing_vs_cv_joint",
                    preferred_tokens=("шрус", "пильник", "шарнір"),
                )
            if _contains_any(product_text, _SHOCK_TERMS):
                return GuardrailHit(
                    code="hub_bearing_vs_shock",
                    preferred_tokens=("амортизатор", "опора амортизатора"),
                )
            if _contains_any(product_text, _GEARBOX_TERMS):
                return GuardrailHit(
                    code="hub_bearing_vs_gearbox_bearing",
                    preferred_tokens=("підшипник кпп", "трансмісія / кпп", "ремкомплект кпп"),
                    prefer_auto_status=True,
                    remap_min_confidence=Decimal("0.940"),
                )

        if _is_brake_pads_category(category_text):
            if _contains_any(product_text, _INJECTOR_TERMS):
                return GuardrailHit(
                    code="brake_pads_vs_injector",
                    preferred_tokens=("форсунка", "ремкомплект форсунки"),
                )
            if _contains_any(product_text, _SHOCK_TERMS):
                return GuardrailHit(
                    code="brake_pads_vs_shock",
                    preferred_tokens=("амортизатор", "опора амортизатора"),
                )
            if (
                _contains_any(product_text, _CALIPER_TERMS)
                and _contains_any(product_text, _SPRING_OR_REPAIR_TERMS)
            ):
                return GuardrailHit(
                    code="brake_pads_vs_caliper_repair",
                    preferred_tokens=("ремкомплект супорта", "гальмівний супорт"),
                )

        if _is_cabin_filter_category(category_text) and _contains_any(product_text, _AIR_FILTER_TERMS):
            return GuardrailHit(
                code="cabin_filter_vs_air_filter",
                preferred_tokens=("повітряний фільтр", "фильтр воздушный", "air filter"),
                prefer_auto_status=True,
                remap_min_confidence=Decimal("0.945"),
            )

        return None
