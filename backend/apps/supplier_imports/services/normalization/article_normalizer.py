from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from apps.supplier_imports.models import ArticleNormalizationRule, ImportSource
from apps.supplier_imports.parsers.utils import normalize_article


@dataclass(frozen=True)
class ArticleNormalizationResult:
    original_article: str
    transformed_article: str
    normalized_article: str
    trace: list[dict[str, str]]


class ArticleNormalizerService:
    def __init__(self) -> None:
        self._rules_cache: dict[str, list[ArticleNormalizationRule]] = {}
        self._result_cache: dict[tuple[str, str], ArticleNormalizationResult] = {}
        self._stats: Counter[str] = Counter()

    def normalize(self, *, article: str, source: ImportSource | None = None) -> ArticleNormalizationResult:
        original = (article or "").strip()
        result_cache_key = (self._source_cache_key(source=source), original)
        cached_result = self._result_cache.get(result_cache_key)
        if cached_result is not None:
            self._stats["result_cache_hits"] += 1
            return cached_result

        self._stats["result_cache_misses"] += 1
        current = original
        trace: list[dict[str, str]] = [{"step": "input", "value": original}]

        rules = self._get_rules(source=source)
        for rule in rules:
            before = current
            after = rule.apply(before)
            if after == before:
                continue
            current = after
            trace.append(
                {
                    "step": "rule",
                    "rule_id": str(rule.id),
                    "rule_name": rule.name,
                    "rule_type": rule.rule_type,
                    "before": before,
                    "after": after,
                }
            )

        transformed = current
        normalized = normalize_article(transformed)
        trace.append(
            {
                "step": "final",
                "transformed": transformed,
                "normalized": normalized,
            }
        )

        result = ArticleNormalizationResult(
            original_article=original,
            transformed_article=transformed,
            normalized_article=normalized,
            trace=trace,
        )
        self._result_cache[result_cache_key] = result
        return result

    def _get_rules(self, *, source: ImportSource | None) -> list[ArticleNormalizationRule]:
        cache_key = self._source_cache_key(source=source)
        cached = self._rules_cache.get(cache_key)
        if cached is not None:
            self._stats["rules_cache_hits"] += 1
            return cached

        self._stats["rules_cache_misses"] += 1
        queryset = ArticleNormalizationRule.objects.filter(is_active=True).select_related("source")
        if source is not None:
            queryset = queryset.filter(source__in=[source, None])
        else:
            queryset = queryset.filter(source__isnull=True)

        rules = list(queryset)
        if source is None:
            rules.sort(key=lambda item: (-item.priority, item.name.lower()))
            self._rules_cache[cache_key] = rules
            return rules

        source_id = str(source.id)

        def rank(item: ArticleNormalizationRule) -> tuple[int, int, str]:
            scope = 0 if item.source_id and str(item.source_id) == source_id else 1
            return (scope, -item.priority, item.name.lower())

        rules.sort(key=rank)
        self._rules_cache[cache_key] = rules
        return rules

    def cache_stats(self) -> dict[str, int]:
        return {
            **dict(self._stats),
            "rules_cache_size": len(self._rules_cache),
            "result_cache_size": len(self._result_cache),
        }

    @staticmethod
    def _source_cache_key(*, source: ImportSource | None) -> str:
        return str(source.id) if source is not None else "__global__"
