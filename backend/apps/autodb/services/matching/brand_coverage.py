from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.matching.brand_resolver import AutoDbBrandResolution, AutoDbBrandResolver
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class AutoDbBrandCoverageRow:
    supplier_code: str
    raw_brand: str
    normalized_raw_brand: str
    product_count: int
    stock_gt_0_count: int
    product_price_count: int
    local_autodb_candidate: str
    resolver_source: str
    existing_alias: str
    decision: str
    recommended_action: str


class AutoDbBrandCoverageAuditService:
    def __init__(self, *, resolver: AutoDbBrandResolver | None = None):
        self.resolver = resolver or AutoDbBrandResolver()

    def audit(self, *, supplier_code: str = "", limit: int = 0) -> list[AutoDbBrandCoverageRow]:
        groups: dict[tuple[str, str], dict[str, object]] = defaultdict(
            lambda: {"product_ids": set(), "stock_gt_0": 0, "raw_brand": "", "bound_supplier_ids": set()}
        )
        queryset = SupplierOffer.objects.select_related("supplier", "product").order_by("supplier__code", "product__display_brand_name")
        if supplier_code:
            queryset = queryset.filter(supplier__code=supplier_code)
        if limit:
            queryset = queryset[: max(int(limit), 1)]

        for offer in queryset:
            raw_brand = offer.product.display_brand_name or offer.product.display_brand_name or product.autodb_supplier_name or "" or offer.product.normalized_brand
            key = (offer.supplier.code, normalize_brand(raw_brand))
            data = groups[key]
            data["raw_brand"] = raw_brand
            data["product_ids"].add(offer.product_id)
            if int(offer.product.autodb_supplier_id or 0) > 0:
                data["bound_supplier_ids"].add(int(offer.product.autodb_supplier_id))
            if int(offer.stock_qty or 0) > 0:
                data["stock_gt_0"] = int(data["stock_gt_0"]) + 1

        rows: list[AutoDbBrandCoverageRow] = []
        for (code, normalized), data in sorted(groups.items()):
            raw_brand = str(data["raw_brand"] or "")
            product_ids = set(data["product_ids"])
            bound_supplier_ids = sorted({int(item) for item in data["bound_supplier_ids"] if int(item or 0) > 0})
            if len(bound_supplier_ids) > 1:
                resolution = AutoDbBrandResolution(
                    raw_brand=raw_brand,
                    normalized_brand=normalized,
                    supplier_code=code,
                    status="skipped_unsafe_ambiguous",
                    decision="unsafe_ambiguous",
                    reason="conflicting Product.autodb_supplier_id values in brand group",
                    resolver_source="product_autodb_supplier_id",
                )
            else:
                resolution = self.resolver.resolve(
                    raw_brand=raw_brand,
                    supplier_code=code,
                    product_autodb_supplier_id=bound_supplier_ids[0] if bound_supplier_ids else None,
                )
            alias = self._existing_alias(normalized)
            rows.append(
                AutoDbBrandCoverageRow(
                    supplier_code=code,
                    raw_brand=raw_brand,
                    normalized_raw_brand=normalized,
                    product_count=len(product_ids),
                    stock_gt_0_count=int(data["stock_gt_0"]),
                    product_price_count=ProductPrice.objects.filter(product_id__in=product_ids).count() if product_ids else 0,
                    local_autodb_candidate=self._candidate_summary(resolution),
                    resolver_source=resolution.resolver_source or "",
                    existing_alias=alias,
                    decision=self._coverage_decision(resolution.decision),
                    recommended_action=self._recommended_action(resolution.decision),
                )
            )
        return rows

    def _existing_alias(self, normalized: str) -> str:
        alias = (
            AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalized, is_active=True)
            .order_by("-manual_confirmed", "-confidence")
            .first()
        )
        if alias is None:
            return ""
        return f"{alias.autodb_supplier_id}:{alias.autodb_supplier_name or ''}".strip(":")

    def _candidate_summary(self, resolution) -> str:
        if resolution.supplier_id is not None:
            return f"{resolution.supplier_id}:{resolution.supplier_name}"
        if resolution.candidates:
            return "; ".join(f"{item['supplier_id']}:{item['name']}" for item in resolution.candidates)
        return ""

    def _coverage_decision(self, decision: str) -> str:
        if decision in {
            "mapped",
            "needs_alias",
            "non_tecdoc",
            "invalid_brand_value",
            "keep_unmapped_missing_supplier",
            "split_brand_needed",
            "unsafe_ambiguous",
            "needs_human_approval",
        }:
            return decision
        return "needs_human_approval"

    def _recommended_action(self, decision: str) -> str:
        return {
            "mapped": "use resolved supplier_id in matching queue",
            "needs_alias": "create approved Auto_DB supplier alias",
            "non_tecdoc": "skip from TecDoc pipeline",
            "invalid_brand_value": "mark invalid brand value and exclude from TecDoc queue",
            "keep_unmapped_missing_supplier": "keep unmapped until Auto_DB supplier exists",
            "split_brand_needed": "split raw brand into concrete TecDoc suppliers",
            "unsafe_ambiguous": "manual approval required; do not alias blindly",
            "needs_human_approval": "review and approve explicit mapping decision",
        }.get(decision, "review and approve explicit mapping decision")
