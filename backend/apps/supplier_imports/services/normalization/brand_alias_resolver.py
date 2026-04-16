from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource, SupplierBrandAlias
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class BrandNormalizationResult:
    original_brand: str
    canonical_brand: str
    normalized_brand: str
    alias_id: str | None
    trace: list[dict[str, str]]


class BrandAliasResolverService:
    def resolve(
        self,
        *,
        brand_name: str,
        source: ImportSource | None = None,
        supplier: Supplier | None = None,
    ) -> BrandNormalizationResult:
        original = (brand_name or "").strip()
        normalized_input = normalize_brand(original)
        trace: list[dict[str, str]] = [
            {
                "step": "input",
                "value": original,
                "normalized": normalized_input,
            }
        ]

        if not normalized_input:
            return BrandNormalizationResult(
                original_brand=original,
                canonical_brand="",
                normalized_brand="",
                alias_id=None,
                trace=trace,
            )

        alias = self._pick_alias(normalized_alias=normalized_input, source=source, supplier=supplier)
        if alias is None:
            trace.append({"step": "alias_not_found", "value": normalized_input})
            return BrandNormalizationResult(
                original_brand=original,
                canonical_brand=original,
                normalized_brand=normalized_input,
                alias_id=None,
                trace=trace,
            )

        canonical = (alias.canonical_brand.name if alias.canonical_brand else alias.canonical_brand_name or original).strip()
        canonical_normalized = normalize_brand(canonical)
        trace.append(
            {
                "step": "alias_applied",
                "alias_id": str(alias.id),
                "canonical_brand": canonical,
                "normalized": canonical_normalized,
            }
        )
        return BrandNormalizationResult(
            original_brand=original,
            canonical_brand=canonical,
            normalized_brand=canonical_normalized,
            alias_id=str(alias.id),
            trace=trace,
        )

    def _pick_alias(
        self,
        *,
        normalized_alias: str,
        source: ImportSource | None,
        supplier: Supplier | None,
    ) -> SupplierBrandAlias | None:
        queryset = SupplierBrandAlias.objects.filter(is_active=True, normalized_alias=normalized_alias)
        if source is not None:
            queryset = queryset.filter(
                Q(source=source)
                | Q(source__isnull=True, supplier=source.supplier)
                | Q(source__isnull=True, supplier__isnull=True)
            )
        elif supplier is not None:
            queryset = queryset.filter(Q(supplier=supplier, source__isnull=True) | Q(supplier__isnull=True, source__isnull=True))
        else:
            queryset = queryset.filter(source__isnull=True, supplier__isnull=True)

        aliases = list(queryset.select_related("canonical_brand", "supplier", "source"))
        if not aliases:
            return None

        if source is not None:
            source_id = str(source.id)
            supplier_id = str(source.supplier_id)
        else:
            source_id = ""
            supplier_id = str(supplier.id) if supplier else ""

        def rank(item: SupplierBrandAlias) -> tuple[int, int]:
            if item.source_id and str(item.source_id) == source_id:
                scope = 0
            elif item.source_id is None and item.supplier_id and str(item.supplier_id) == supplier_id:
                scope = 1
            else:
                scope = 2
            return scope, -item.priority

        aliases.sort(key=rank)
        return aliases[0]
