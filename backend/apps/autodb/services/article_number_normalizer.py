from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ArticleNumberNormalizationResult:
    original: str
    canonical: str
    normalized: str
    search_variants: tuple[str, ...]


class ArticleNumberNormalizer:
    """Builds safe search variants for supplier article numbers."""

    _collapse_ws = re.compile(r"\s+")
    _non_alnum = re.compile(r"[^A-Z0-9]")
    _trailing_digits = re.compile(r"^([A-Z0-9]*[A-Z])([0-9]{2,})$")

    def normalize(self, value: str | None) -> ArticleNumberNormalizationResult:
        original = str(value or "")
        trimmed = self._collapse_ws.sub(" ", original).strip().upper()

        canonical = trimmed.replace(" ", "")
        normalized = self._non_alnum.sub("", canonical)

        variants: list[str] = []

        def add(item: str) -> None:
            text = str(item or "").strip().upper()
            if text and text not in variants:
                variants.append(text)

        add(trimmed)
        add(canonical)
        add(canonical.replace("-", ""))
        add(canonical.replace("/", ""))
        add(canonical.replace("-", "").replace("/", ""))
        add(canonical.replace("/", "-"))
        add(normalized)
        for variant in self._expand_compound_variants(normalized):
            add(variant)

        return ArticleNumberNormalizationResult(
            original=original,
            canonical=canonical,
            normalized=normalized,
            search_variants=tuple(variants),
        )

    def _expand_compound_variants(self, compact: str) -> tuple[str, ...]:
        if not compact:
            return ()
        variants: list[str] = []

        def add(item: str) -> None:
            text = str(item or "").strip().upper()
            if text and text not in variants:
                variants.append(text)

        boundaries = self._alpha_digit_boundaries(compact)
        for idx in boundaries:
            left = compact[:idx]
            right = compact[idx:]
            add(f"{left} {right}")
            add(f"{left}-{right}")
            trailing = self._split_trailing_digits(right)
            if trailing:
                right_head, right_tail = trailing
                add(f"{left} {right_head}-{right_tail}")
                add(f"{left}-{right_head}-{right_tail}")

        trailing = self._split_trailing_digits(compact)
        if trailing:
            head, tail = trailing
            add(f"{head} {tail}")
            add(f"{head}-{tail}")

        return tuple(variants)

    def _alpha_digit_boundaries(self, value: str) -> tuple[int, ...]:
        indexes: list[int] = []
        for idx in range(1, len(value)):
            prev_char = value[idx - 1]
            next_char = value[idx]
            if prev_char.isalpha() and next_char.isdigit():
                indexes.append(idx)
            elif prev_char.isdigit() and next_char.isalpha():
                indexes.append(idx)
        return tuple(indexes)

    def _split_trailing_digits(self, value: str) -> tuple[str, str] | None:
        match = self._trailing_digits.match(value)
        if not match:
            return None
        return match.group(1), match.group(2)
