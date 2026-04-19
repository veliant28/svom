from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata

SIGNAL_KEYWORDS = (
    "category",
    "group",
    "катег",
    "груп",
    "section",
    "segment",
    "подгруп",
)

SPLIT_RE = re.compile(r"[>|/\\]+")
TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯіІїЇєЄ0-9]+", flags=re.UNICODE)
STOP_TOKENS = {
    "для",
    "for",
    "and",
    "the",
    "with",
    "без",
    "комплект",
    "набір",
    "set",
    "kit",
}
TITLE_SIGNATURE_TOKEN_LIMIT = 5
TOKEN_SIGNAL_LIMIT = 12


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[\s_]+", " ", text)
    text = re.sub(r"[^\w\s/>\\|.-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(value: str) -> set[str]:
    normalized = normalize_text(value)
    tokens = {
        token
        for token in TOKEN_RE.findall(normalized)
        if len(token) >= 3 and token not in STOP_TOKENS
    }
    return tokens


def to_confidence(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    decimal_value = Decimal(str(value))
    return decimal_value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def build_title_signature(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    tokens = [token for token in TOKEN_RE.findall(normalized) if len(token) >= 3 and token not in STOP_TOKENS]
    if not tokens:
        return ""
    return " ".join(tokens[:TITLE_SIGNATURE_TOKEN_LIMIT])


def extract_category_signals(raw_payload: dict) -> list[str]:
    collected: list[str] = []

    def walk(value, *, key_name: str = "") -> None:
        if isinstance(value, dict):
            for key, nested_value in value.items():
                walk(nested_value, key_name=str(key))
            return

        if isinstance(value, list):
            for item in value:
                walk(item, key_name=key_name)
            return

        if value is None:
            return

        key_normalized = normalize_text(key_name)
        if not any(keyword in key_normalized for keyword in SIGNAL_KEYWORDS):
            return

        text = str(value).strip()
        if not text:
            return
        if len(text) > 255:
            text = text[:255]
        collected.append(text)

    walk(raw_payload)

    unique: list[str] = []
    seen: set[str] = set()
    for item in collected:
        normalized = normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(item)
    return unique[:20]


def iter_signal_variants(raw_payload: dict) -> set[str]:
    variants: set[str] = set()
    for signal in extract_category_signals(raw_payload):
        normalized_signal = normalize_text(signal)
        if not normalized_signal:
            continue
        variants.add(normalized_signal)
        split_items = [item.strip() for item in SPLIT_RE.split(normalized_signal) if item.strip()]
        if split_items:
            variants.add(split_items[-1])
    return variants
