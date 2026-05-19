from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
import re
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings

from apps.autodb.models import AutoDbTranslationSettings
from apps.autodb.selectors import get_autodb_translation_settings, has_autodb_translation_settings_table
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
    _protected_token_re = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9./+\-]{1,})\b")
    _wiper_variants_by_lang: dict[str, tuple[str, ...]] = {
        "uk": (
            "щітка склоочисника",
            "вітровий склоочисник щітка",
            "склоочисник щітка",
        ),
        "ru": (
            "щетка стеклоочистителя",
            "дворники",
        ),
        "en": (
            "wiper blade",
            "wiper brush",
            "windscreen wiper",
        ),
    }
    _wiper_base_by_lang: dict[str, str] = {
        "uk": "Щітка склоочисника",
        "ru": "Щетка стеклоочистителя",
        "en": "Wiper blade",
    }
    _legacy_placeholder_re = re.compile(r"__AUTODB_TOKEN_(\d+)__", re.IGNORECASE)
    _translated_placeholder_token_re = r"(?:auto\s*db|autodb|автодб|автод)(?:[\W_]*(?:token|токен|тоен))?"
    _cyrillic_re = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")
    _english_cyrillic_term_replacements: tuple[tuple[str, str], ...] = (
        (r"\bВАЗ\b", "VAZ"),
        (r"\bГАЗ\b", "GAZ"),
        (r"\bУАЗ\b", "UAZ"),
        (r"\bЗАЗ\b", "ZAZ"),
        (r"\bЗІЛ\b", "ZIL"),
        (r"\bЗИЛ\b", "ZIL"),
        (r"\bАЗЛК\b", "AZLK"),
        (r"\bІЖ\b", "IZH"),
        (r"\bИЖ\b", "IZH"),
        (r"\bдовгий\b", "long"),
        (r"\bдовга\b", "long"),
        (r"\bдовге\b", "long"),
        (r"\bдовгі\b", "long"),
    )

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
        protected_tokens = self._extract_protected_tokens(clean)
        uk = clean
        ru = clean
        en = clean
        translated = False

        mapped = self._load_translation_index().get(self._normalize_key(clean))
        if mapped:
            uk, ru, en = mapped
            translated = True

        if not translated and self._is_offline_translate_enabled():
            offline = self._translate_via_offline_api(
                source_text=clean,
                source_lang=lang,
                protected_tokens=protected_tokens,
            )
            if offline is not None:
                uk, ru, en = offline
                translated = True

        uk, ru, en = self._normalize_domain_translation(
            source_text=clean,
            source_lang=lang,
            uk=uk,
            ru=ru,
            en=en,
        )
        uk, ru, en = self._apply_headword_translation_for_latin_suffix(
            source_text=clean,
            uk=uk,
            ru=ru,
            en=en,
        )
        uk, ru, en = self._ensure_protected_tokens(
            source_text=clean,
            uk=uk,
            ru=ru,
            en=en,
        )
        en = self._normalize_english_cyrillic_terms(en=en)

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

    def _translate_via_offline_api(
        self,
        *,
        source_text: str,
        source_lang: str,
        protected_tokens: list[str],
    ) -> tuple[str, str, str] | None:
        provider = self._get_translate_provider()
        if provider == AutoDbTranslationSettings.PROVIDER_GOOGLE:
            return self._translate_via_google_api(
                source_text=source_text,
                source_lang=source_lang,
                protected_tokens=protected_tokens,
            )
        return self._translate_via_libretranslate_api(
            source_text=source_text,
            source_lang=source_lang,
            protected_tokens=protected_tokens,
        )

    def _translate_via_libretranslate_api(
        self,
        *,
        source_text: str,
        source_lang: str,
        protected_tokens: list[str],
    ) -> tuple[str, str, str] | None:
        base_url = str(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_URL", "http://libretranslate:5000")).strip().rstrip("/")
        if not base_url:
            return None
        api_key = str(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_API_KEY", "") or "").strip()
        timeout_ms = int(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS", 4000) or 4000)
        timeout_s = max(timeout_ms, 500) / 1000.0

        source_code = source_lang if source_lang in {"ru", "uk", "en"} else "auto"
        masked_source, placeholders = self._mask_protected_tokens(source_text=source_text, protected_tokens=protected_tokens)

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
                text=masked_source,
                timeout_s=timeout_s,
            )
            if not translated:
                return None
            restored = self._restore_placeholders(translated_text=translated, placeholders=placeholders)
            translated_values[target] = source_text if self._has_placeholder_artifact(restored) else restored

        uk = sanitize_product_name(translated_values.get("uk") or source_text)
        ru = sanitize_product_name(translated_values.get("ru") or source_text)
        en = sanitize_product_name(translated_values.get("en") or source_text)
        if not uk or not ru or not en:
            return None
        return uk, ru, en

    def _translate_via_google_api(
        self,
        *,
        source_text: str,
        source_lang: str,
        protected_tokens: list[str],
    ) -> tuple[str, str, str] | None:
        base_url = str(
            getattr(
                settings,
                "AUTODB_GOOGLE_TRANSLATE_URL",
                "https://translation.googleapis.com/language/translate/v2",
            )
            or ""
        ).strip()
        if not base_url:
            return None
        api_key = self._get_google_api_key()
        if not api_key:
            return None
        timeout_ms = int(getattr(settings, "AUTODB_OFFLINE_TRANSLATE_TIMEOUT_MS", 4000) or 4000)
        timeout_s = max(timeout_ms, 500) / 1000.0

        source_code = source_lang if source_lang in {"ru", "uk", "en"} else "auto"
        masked_source, placeholders = self._mask_protected_tokens(source_text=source_text, protected_tokens=protected_tokens)
        translated_values: dict[str, str] = {}
        for target in ("uk", "ru", "en"):
            if source_code == target:
                translated_values[target] = source_text
                continue
            translated = self._google_translate_text(
                base_url=base_url,
                api_key=api_key,
                source=source_code,
                target=target,
                text=masked_source,
                timeout_s=timeout_s,
            )
            if not translated:
                return None
            restored = self._restore_placeholders(translated_text=translated, placeholders=placeholders)
            translated_values[target] = source_text if self._has_placeholder_artifact(restored) else restored

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

    def _get_translation_settings(self) -> AutoDbTranslationSettings | None:
        try:
            if not has_autodb_translation_settings_table():
                return None
            return get_autodb_translation_settings()
        except Exception:
            return None

    def _get_translate_provider(self) -> str:
        fallback_provider = str(
            getattr(settings, "AUTODB_OFFLINE_TRANSLATE_PROVIDER", AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE)
            or AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE
        ).strip().lower()
        if fallback_provider not in {
            AutoDbTranslationSettings.PROVIDER_GOOGLE,
            AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE,
        }:
            fallback_provider = AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE
        translation_settings = self._get_translation_settings()
        if translation_settings is None:
            return fallback_provider
        provider = str(translation_settings.provider or "").strip().lower()
        if provider in {
            AutoDbTranslationSettings.PROVIDER_GOOGLE,
            AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE,
        }:
            return provider
        return fallback_provider

    def _get_google_api_key(self) -> str:
        translation_settings = self._get_translation_settings()
        if translation_settings is not None:
            from_db = str(translation_settings.google_api_key or "").strip()
            if from_db:
                return from_db
        return str(getattr(settings, "AUTODB_GOOGLE_TRANSLATE_API_KEY", "") or "").strip()

    def _google_translate_text(
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
            "target": target,
            "format": "text",
        }
        if source != "auto":
            payload["source"] = source

        delimiter = "&" if "?" in base_url else "?"
        request = urllib_request.Request(
            url=f"{base_url}{delimiter}key={api_key}",
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
        items = data.get("data", {}).get("translations", [])
        if not isinstance(items, list) or not items:
            return ""
        translated_raw = str((items[0] or {}).get("translatedText") or "")
        translated = sanitize_product_name(html.unescape(translated_raw))
        return translated[:255]

    def _extract_protected_tokens(self, value: str) -> list[str]:
        out: list[str] = []
        for match in self._protected_token_re.finditer(str(value or "")):
            token = sanitize_product_name(match.group(1))
            if not token:
                continue
            if not self._is_protected_token(token):
                continue
            if token.upper() in {item.upper() for item in out}:
                continue
            out.append(token)
        return out

    def _is_protected_token(self, token: str) -> bool:
        if not token:
            return False
        if any(char.isdigit() for char in token):
            return True
        if token.upper() == token and len(token) >= 2:
            return True
        if "-" in token and any(char.isupper() for char in token):
            return True
        return False

    def _mask_protected_tokens(self, *, source_text: str, protected_tokens: list[str]) -> tuple[str, dict[str, str]]:
        text = str(source_text or "")
        placeholders: dict[str, str] = {}
        for index, token in enumerate(protected_tokens):
            placeholder = f"@@AUTODB{index}@@"
            placeholders[placeholder] = token
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", flags=re.IGNORECASE)
            text = pattern.sub(placeholder, text)
        return text, placeholders

    def _restore_placeholders(self, *, translated_text: str, placeholders: dict[str, str]) -> str:
        text = str(translated_text or "")
        ordered_tokens: list[tuple[int, str]] = []
        for placeholder, token in placeholders.items():
            text = text.replace(placeholder, token)
            legacy_match = self._legacy_placeholder_re.fullmatch(placeholder.strip())
            if legacy_match:
                ordered_tokens.append((int(legacy_match.group(1)), token))
                continue
            modern_match = re.fullmatch(r"@@AUTODB(\d+)@@", placeholder.strip(), flags=re.IGNORECASE)
            if modern_match:
                ordered_tokens.append((int(modern_match.group(1)), token))

        for index, token in ordered_tokens:
            compact_placeholder_pattern = re.compile(
                rf"@*\s*(?:auto\s*db|autodb|автодб|автод)[\W_]*(?:token|токен|тоен)?[\W_]*{index}(?:st|nd|rd|th)?\s*@*",
                flags=re.IGNORECASE,
            )
            text = compact_placeholder_pattern.sub(token, text)
            translated_pattern = re.compile(
                rf"\b{self._translated_placeholder_token_re}[\W_]*{index}(?:st|nd|rd|th)?\b",
                flags=re.IGNORECASE,
            )
            text = translated_pattern.sub(token, text)

        # If placeholder artifacts survive translation, drop them.
        text = re.sub(
            rf"\b{self._translated_placeholder_token_re}[\W_]*\d+(?:st|nd|rd|th)?\b",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"@+\s*autodb\s*\d+\s*@+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = text.replace("@", "")

        # Collapse tail duplicates like "... A-line 15 A-line 15".
        token_tail = " ".join(token for _, token in sorted(ordered_tokens, key=lambda item: item[0])).strip()
        if token_tail:
            repeated_tail = f"{token_tail} {token_tail}"
            if text.lower().endswith(repeated_tail.lower()):
                text = text[: -len(repeated_tail)].rstrip()
                text = sanitize_product_name(f"{text} {token_tail}")

        # Restore spacing for accidentally glued protected tokens, e.g. "A-line12".
        sorted_tokens = [token for _, token in sorted(ordered_tokens, key=lambda item: item[0]) if token]
        for left, right in zip(sorted_tokens, sorted_tokens[1:]):
            glued_pattern = re.compile(
                rf"{re.escape(left)}\s*{re.escape(right)}",
                flags=re.IGNORECASE,
            )
            text = glued_pattern.sub(f"{left} {right}", text)
        for token in sorted_tokens:
            duplicate_pattern = re.compile(
                rf"({re.escape(token)})\s+\1",
                flags=re.IGNORECASE,
            )
            text = duplicate_pattern.sub(token, text)
            duplicate_compact_pattern = re.compile(
                rf"({re.escape(token)})\1",
                flags=re.IGNORECASE,
            )
            text = duplicate_compact_pattern.sub(token, text)

        normalized = sanitize_product_name(text)
        lowered = normalized.lower()
        if normalized and len(normalized) % 2 == 0:
            half = len(normalized) // 2
            if lowered[:half] == lowered[half:]:
                normalized = normalized[:half]

        return sanitize_product_name(normalized)

    def _has_placeholder_artifact(self, value: str) -> bool:
        return bool(
            re.search(
                rf"\b{self._translated_placeholder_token_re}[\W_]*\d+\b",
                str(value or ""),
                flags=re.IGNORECASE,
            )
        )

    def _apply_headword_translation_for_latin_suffix(
        self,
        *,
        source_text: str,
        uk: str,
        ru: str,
        en: str,
    ) -> tuple[str, str, str]:
        source = sanitize_product_name(source_text)
        if not source:
            return uk, ru, en

        # Keep this normalization scoped to names like:
        # "Амортизатор MONROE ORIGINAL (Gas Technology)"
        # where the suffix is a Latin/brand tail that should stay untouched.
        match = re.match(r"^\s*([А-Яа-яЁёІіЇїЄєҐґ\s\-/'`]+?)\s+(.+)$", source)
        if not match:
            return uk, ru, en

        head = sanitize_product_name(match.group(1))
        suffix = sanitize_product_name(match.group(2))
        if not head or not suffix:
            return uk, ru, en
        if not re.search(r"[A-Za-z0-9]", suffix):
            return uk, ru, en
        if self._cyrillic_re.search(suffix):
            return uk, ru, en

        mapped = self._load_translation_index().get(self._normalize_key(head))
        if not mapped:
            return uk, ru, en

        mapped_uk, mapped_ru, mapped_en = mapped
        return (
            sanitize_product_name(f"{mapped_uk} {suffix}")[:255],
            sanitize_product_name(f"{mapped_ru} {suffix}")[:255],
            sanitize_product_name(f"{mapped_en} {suffix}")[:255],
        )

    def _contains_wiper_term(self, *, value: str) -> bool:
        lower = str(value or "").lower()
        for variants in self._wiper_variants_by_lang.values():
            for candidate in variants:
                if candidate and candidate in lower:
                    return True
        return False

    def _normalize_domain_translation(
        self,
        *,
        source_text: str,
        source_lang: str,
        uk: str,
        ru: str,
        en: str,
    ) -> tuple[str, str, str]:
        if not self._contains_wiper_term(value=source_text):
            return uk, ru, en

        current = {
            "uk": sanitize_product_name(uk),
            "ru": sanitize_product_name(ru),
            "en": sanitize_product_name(en),
        }
        for lang in ("uk", "ru", "en"):
            suffix = self._extract_wiper_suffix(text=current[lang], lang=lang)
            if not suffix:
                suffix = self._extract_wiper_suffix(text=source_text, lang=source_lang)
            base = self._wiper_base_by_lang[lang]
            current[lang] = self._compose_base_and_suffix(base=base, suffix=suffix)
        return current["uk"], current["ru"], current["en"]

    def _extract_wiper_suffix(self, *, text: str, lang: str) -> str:
        clean = sanitize_product_name(text)
        variants = self._wiper_variants_by_lang.get(lang, ())
        for variant in variants:
            pattern = re.compile(rf"\b{re.escape(variant)}\b", flags=re.IGNORECASE)
            match = pattern.search(clean)
            if not match:
                continue
            prefix = sanitize_product_name(clean[: match.start()].strip(" ,.;:-"))
            suffix = sanitize_product_name(clean[match.end() :].strip(" ,.;:-"))
            if suffix and prefix:
                return sanitize_product_name(f"{prefix} {suffix}")
            if suffix:
                return suffix
            if prefix:
                return prefix
            return ""
        return ""

    def _compose_base_and_suffix(self, *, base: str, suffix: str) -> str:
        base_clean = sanitize_product_name(base)
        suffix_clean = sanitize_product_name(suffix)
        if not suffix_clean:
            return base_clean
        if suffix_clean.lower() in base_clean.lower():
            return base_clean
        return sanitize_product_name(f"{base_clean} {suffix_clean}")[:255]

    def _ensure_protected_tokens(self, *, source_text: str, uk: str, ru: str, en: str) -> tuple[str, str, str]:
        protected_tokens = self._extract_protected_tokens(source_text)
        values: dict[str, str] = {
            "uk": sanitize_product_name(uk),
            "ru": sanitize_product_name(ru),
            "en": sanitize_product_name(en),
        }
        for lang in ("uk", "ru", "en"):
            current = values[lang]
            for token in protected_tokens:
                if token.upper() in current.upper():
                    continue
                current = sanitize_product_name(f"{current} {token}")
            values[lang] = current[:255]
        return values["uk"], values["ru"], values["en"]

    def _normalize_english_cyrillic_terms(self, *, en: str) -> str:
        text = sanitize_product_name(en or "")
        if not text or not self._cyrillic_re.search(text):
            return text

        for pattern, replacement in self._english_cyrillic_term_replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        text = re.sub(r"\s{2,}", " ", text).strip()
        return sanitize_product_name(text)[:255]
