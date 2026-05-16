from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings

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

        if not translated and self._is_offline_translate_enabled():
            offline = self._translate_via_offline_api(source_text=clean, source_lang=lang)
            if offline is not None:
                uk, ru, en = offline
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
        if re.search(r"[а-я]", lower):
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

    def _is_offline_translate_enabled(self) -> bool:
        return bool(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_ENABLED", False))

    def _translate_via_offline_api(self, *, source_text: str, source_lang: str) -> tuple[str, str, str] | None:
        base_url = str(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_URL", "http://libretranslate:5000")).strip().rstrip("/")
        if not base_url:
            return None
        api_key = str(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_API_KEY", "") or "").strip()
        timeout_ms = int(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS", 4000) or 4000)
        timeout_s = max(timeout_ms, 500) / 1000.0

        source_code = source_lang if source_lang in {"ru", "uk", "en"} else "auto"

        translated_values: dict[str, str] = {}
        for target in ("uk", "ru", "en"):
            if source_code == target:
                translated_values[target] = source_text
                continue
            translated = self._offline_translate_text(
                base_url=base_url,
                api_key=api_key,
                source=source_code,
                target=target,
                text=source_text,
                timeout_s=timeout_s,
            )
            if not translated:
                return None
            translated_values[target] = translated

        uk = sanitize_product_name(translated_values.get("uk") or source_text)
        ru = sanitize_product_name(translated_values.get("ru") or source_text)
        en = sanitize_product_name(translated_values.get("en") or source_text)
        if not uk or not ru or not en:
            return None
        return uk, ru, en

    def _offline_translate_text(
        self,
        *,
        base_url: str,
        api_key: str,
        source: str,
        target: str,
        text: str,
        timeout_s: float,
    ) -> str:
        payload: dict[str, str] = {
            "q": text,
            "source": source,
            "target": target,
            "format": "text",
        }
        if api_key:
            payload["api_key"] = api_key

        request = urllib_request.Request(
            url=f"{base_url}/translate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                body = response.read().decode("utf-8")
        except (urllib_error.URLError, TimeoutError, OSError):
            return ""

        try:
            data = json.loads(body)
        except ValueError:
            return ""
        translated = sanitize_product_name(str(data.get("translatedText") or ""))
        return translated[:255]
