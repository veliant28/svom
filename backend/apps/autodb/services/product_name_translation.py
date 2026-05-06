from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from apps.catalog.services.product_management import sanitize_product_name


@dataclass(frozen=True)
class ProductNameTranslationResult:
    uk: str
    ru: str
    en: str
    status: str
    error: str = ""
    source_lang: str = ""


class ProductNameTranslationService:
    """Local translation abstraction with safe fallback and no external calls by default."""

    _cache: dict[str, tuple[str, str, str]] | None = None

    def translate_product_name(self, *, source_text: str, source_lang: str | None = None) -> ProductNameTranslationResult:
        clean = sanitize_product_name(source_text or "")
        if not clean:
            return ProductNameTranslationResult(
                uk="",
                ru="",
                en="",
                status="failed",
                error="empty_source_text",
            )

        lang = (source_lang or "").strip().lower() or self._detect_language(clean)
        uk = clean
        ru = clean
        en = clean
        translated = False

        mapped = self._load_translation_index().get(self._normalize_key(clean))
        if mapped:
            uk, ru, en = mapped
            translated = True

        status = "translated" if translated else "pending"
        return ProductNameTranslationResult(
            uk=sanitize_product_name(uk)[:255],
            ru=sanitize_product_name(ru)[:255],
            en=sanitize_product_name(en)[:255],
            status=status,
            error="" if translated else "translation_not_found_in_dictionary",
            source_lang=lang,
        )

    def _detect_language(self, value: str) -> str:
        text = str(value or "")
        lower = text.lower()
        if re.search(r"[іїєґ]", lower):
            return "uk"
        if re.search(r"[ыэёъ]", lower):
            return "ru"
        if re.search(r"[a-z]", lower):
            return "en"
        return "uk"

    def _load_translation_index(self) -> dict[str, tuple[str, str, str]]:
        if self._cache is not None:
            return self._cache

        path = Path(__file__).resolve().parents[1] / "data" / "product_name_translations.json"
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw_data = []

        index: dict[str, tuple[str, str, str]] = {}
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            uk = sanitize_product_name(str(item.get("uk") or ""))
            ru = sanitize_product_name(str(item.get("ru") or ""))
            en = sanitize_product_name(str(item.get("en") or ""))
            if not uk or not ru or not en:
                continue
            variants = [uk, ru, en]
            aliases = item.get("aliases") or []
            if isinstance(aliases, list):
                variants.extend(str(alias or "") for alias in aliases)
            for value in variants:
                key = self._normalize_key(value)
                if key:
                    index[key] = (uk[:255], ru[:255], en[:255])

        self._cache = index
        return self._cache

    def _normalize_key(self, value: str) -> str:
        normalized = sanitize_product_name(value or "").lower()
        normalized = normalized.replace("ё", "е")
        return normalized
