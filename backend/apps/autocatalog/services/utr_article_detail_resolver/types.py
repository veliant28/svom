from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class UtrArticleResolveSummary:
    article_pairs_total: int = 0
    article_pairs_processed: int = 0
    resolved_created: int = 0
    resolved_updated: int = 0
    already_resolved: int = 0
    unresolved_created: int = 0
    unresolved_updated: int = 0
    empty_results: int = 0
    ambiguous_results: int = 0
    failed_requests: int = 0
    stopped_due_to_circuit_breaker: int = 0
    resolve_batches_sent_total: int = 0
    resolve_pairs_sent_total: int = 0
    resolve_pairs_resolved_total: int = 0
    resolve_pairs_unresolved_total: int = 0
    resolve_pairs_ambiguous_total: int = 0
    resolve_batch_failures_total: int = 0
    resolve_batch_auth_failures_total: int = 0
    resolve_pairs_auth_failures_total: int = 0
    resolve_pairs_transport_failures_total: int = 0
    resolve_pairs_supplier_errors_total: int = 0
    resolved_products_enriched_total: int = 0
    resolved_product_images_created_total: int = 0
    stage_primary_brandless_attempted_total: int = 0
    stage_primary_brandless_resolved_total: int = 0
    stage_fallback_brandless_attempted_total: int = 0
    stage_fallback_brandless_resolved_total: int = 0
    stage_primary_branded_attempted_total: int = 0
    stage_primary_branded_resolved_total: int = 0
    stage_fallback_branded_attempted_total: int = 0
    stage_fallback_branded_resolved_total: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class UtrArticleResolveProgress:
    raw_pairs_total: int = 0
    mapped_pairs_total: int = 0
    mapped_pairs_resolved: int = 0
    mapped_pairs_unresolved: int = 0
    raw_pairs_unattempted: int = 0
    raw_pairs_unresolved_total: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class ResolveContext:
    pair: dict[str, str]
    stages: list[dict[str, str]]
    status: str = "pending"
    detail_id: str = ""
    detail_payload: dict | None = None
    resolved_stage: str = ""
    auth_failed: bool = False
    transport_failed: bool = False
    supplier_error: bool = False
    error_message: str = ""
