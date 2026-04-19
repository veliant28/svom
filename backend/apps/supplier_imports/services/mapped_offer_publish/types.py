from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SupplierMappedPublishResult:
    supplier_code: str
    supplier_name: str
    raw_rows_scanned: int
    unique_latest_rows: int
    eligible_rows: int
    created_rows: int
    updated_rows: int
    skipped_rows: int
    error_rows: int
    products_created: int
    products_updated: int
    offers_created: int
    offers_updated: int
    raw_offer_links_updated: int
    repriced_products: int
    repricing_stats: dict[str, int]
    skip_reasons: dict[str, int]
    error_reasons: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "supplier_code": self.supplier_code,
            "supplier_name": self.supplier_name,
            "raw_rows_scanned": self.raw_rows_scanned,
            "unique_latest_rows": self.unique_latest_rows,
            "eligible_rows": self.eligible_rows,
            "created_rows": self.created_rows,
            "updated_rows": self.updated_rows,
            "skipped_rows": self.skipped_rows,
            "error_rows": self.error_rows,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "offers_created": self.offers_created,
            "offers_updated": self.offers_updated,
            "raw_offer_links_updated": self.raw_offer_links_updated,
            "repriced_products": self.repriced_products,
            "repricing_stats": self.repricing_stats,
            "skip_reasons": self.skip_reasons,
            "error_reasons": self.error_reasons,
        }


@dataclass
class PublishCounters:
    raw_rows_scanned: int = 0
    unique_latest_rows: int = 0
    eligible_rows: int = 0
    created_rows: int = 0
    updated_rows: int = 0
    skipped_rows: int = 0
    error_rows: int = 0
    products_created: int = 0
    products_updated: int = 0
    offers_created: int = 0
    offers_updated: int = 0
    raw_offer_links_updated: int = 0
    repriced_products: int = 0
    repricing_stats: dict[str, int] = field(default_factory=dict)
    skip_reasons: dict[str, int] = field(default_factory=dict)
    error_reasons: dict[str, int] = field(default_factory=dict)

    def add_skip(self, reason: str) -> None:
        self.skipped_rows += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1

    def add_error(self, reason: str) -> None:
        self.error_rows += 1
        self.error_reasons[reason] = self.error_reasons.get(reason, 0) + 1
