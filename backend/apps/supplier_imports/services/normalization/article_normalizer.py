from __future__ import annotations
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
    def normalize(self, *, article: str, source: ImportSource | None = None) -> ArticleNormalizationResult:
        original = (article or "").strip()
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

        return ArticleNormalizationResult(
            original_article=original,
            transformed_article=transformed,
            normalized_article=normalized,
            trace=trace,
        )

    def _get_rules(self, *, source: ImportSource | None) -> list[ArticleNormalizationRule]:
        queryset = ArticleNormalizationRule.objects.filter(is_active=True).select_related("source")
        if source is not None:
            queryset = queryset.filter(source__in=[source, None])
        else:
            queryset = queryset.filter(source__isnull=True)

        rules = list(queryset)
        if source is None:
            rules.sort(key=lambda item: (-item.priority, item.name.lower()))
            return rules

        source_id = str(source.id)

        def rank(item: ArticleNormalizationRule) -> tuple[int, int, str]:
            scope = 0 if item.source_id and str(item.source_id) == source_id else 1
            return (scope, -item.priority, item.name.lower())

        rules.sort(key=rank)
        return rules
