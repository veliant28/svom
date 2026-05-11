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
    _separator_re = re.compile(r"[\s\-_/\\\.,\u2010\u2011\u2012\u2013\u2014\u2015\u2212]+")
    _trailing_digits = re.compile(r"^([A-Z0-9]*[A-Z])([0-9]{2,})$")
    _cyr_to_latin = str.maketrans(
        {
            "А": "A",
            "В": "B",
            "С": "C",
            "Е": "E",
            "Н": "H",
            "К": "K",
            "М": "M",
            "О": "O",
            "Р": "P",
            "Т": "T",
            "Х": "X",
            "У": "Y",
        }
    )
    _latin_to_cyr = str.maketrans(
        {
            "A": "А",
            "B": "В",
            "C": "С",
            "E": "Е",
            "H": "Н",
            "K": "К",
            "M": "М",
            "O": "О",
            "P": "Р",
            "T": "Т",
            "X": "Х",
            "Y": "У",
        }
    )

    def normalize(self, value: str | None) -> ArticleNumberNormalizationResult:
        original = str(value or "")
        trimmed = self._collapse_ws.sub(" ", original).strip().upper()
        folded = self._fold_to_latin(trimmed)

        canonical = self._separator_re.sub("", folded)
        normalized = self._non_alnum.sub("", canonical)

        variants: list[str] = []

        def add(item: str) -> None:
            text = str(item or "").strip().upper()
            if text and text not in variants:
                variants.append(text)

        add(trimmed)
        add(folded)
        add(trimmed.replace(" ", ""))
        add(folded.replace(" ", ""))
        add(trimmed.replace(" ", "").replace("/", "-"))
        add(folded.replace(" ", "").replace("/", "-"))
        add(canonical)
        add(normalized)
        for variant in self._expand_compound_variants(normalized):
            add(variant)
        for variant in self._to_cyrillic_homoglyph_variants(tuple(variants)):
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
        if boundaries:
            with_spaces = self._insert_boundaries(compact, boundaries=boundaries, separator=" ")
            if with_spaces:
                add(with_spaces)
            with_hyphen = self._insert_boundaries(compact, boundaries=boundaries, separator="-")
            if with_hyphen:
                add(with_hyphen)

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

    def _fold_to_latin(self, value: str) -> str:
        if not value:
            return ""
        return value.translate(self._cyr_to_latin)

    def _to_cyrillic_homoglyph_variants(self, variants: tuple[str, ...]) -> tuple[str, ...]:
        out: list[str] = []
        for item in variants:
            text = str(item or "").strip().upper()
            if not text:
                continue
            converted = text.translate(self._latin_to_cyr)
            if converted != text and converted not in out:
                out.append(converted)
        return tuple(out)

    def _insert_boundaries(self, value: str, *, boundaries: tuple[int, ...], separator: str) -> str:
        if not value or not boundaries:
            return value
        parts: list[str] = []
        start = 0
        for boundary in boundaries:
            parts.append(value[start:boundary])
            start = boundary
        parts.append(value[start:])
        return separator.join(part for part in parts if part)
