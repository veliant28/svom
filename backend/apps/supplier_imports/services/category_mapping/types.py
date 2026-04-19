from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer

AUTO_CONFIDENCE_THRESHOLD = Decimal("0.900")
REVIEW_CONFIDENCE_THRESHOLD = Decimal("0.620")
FORCE_TITLE_SIGNATURE_AUTO_THRESHOLD = Decimal("0.940")

FORCE_RISKY_REASONS = frozenset(
    {
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
    }
)

FORCE_ALWAYS_REVIEW_REASONS = frozenset(
    {
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP,
        SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW,
    }
)


@dataclass(frozen=True)
class CategoryMappingDecision:
    status: str
    reason: str
    category: Category | None
    confidence: Decimal | None


@dataclass(frozen=True)
class CategoryMappingApplyResult:
    status: str
    reason: str
    category_id: str | None
    confidence: Decimal | None
    updated: bool
    skipped_manual: bool = False


@dataclass
class CategoryMappingBulkStats:
    processed: int = 0
    updated: int = 0
    skipped_manual: int = 0
    errors: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    unmapped_reason_counts: dict[str, int] = field(default_factory=dict)

    def bump_status(self, status: str) -> None:
        self.status_counts[status] = self.status_counts.get(status, 0) + 1

    def bump_unmapped_reason(self, reason: str) -> None:
        key = reason or SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL
        self.unmapped_reason_counts[key] = self.unmapped_reason_counts.get(key, 0) + 1


@dataclass(frozen=True)
class CategoryIndexEntry:
    category: Category
    path: str
    path_normalized: str
    is_leaf: bool
    names_normalized: tuple[str, ...]
    token_pool: frozenset[str]
    primary_tokens: frozenset[str]


@dataclass(frozen=True)
class KnowledgeChoice:
    entry: CategoryIndexEntry
    confidence: Decimal


@dataclass(frozen=True)
class ForcedMappingKnowledge:
    default_choice: KnowledgeChoice | None
    supplier_choices: dict[str, KnowledgeChoice]
    supplier_brand_choices: dict[tuple[str, str], KnowledgeChoice]
    brand_choices: dict[str, KnowledgeChoice]
    supplier_signal_choices: dict[tuple[str, str], KnowledgeChoice]
    global_signal_choices: dict[str, KnowledgeChoice]
    title_signature_choices: dict[tuple[str, str, str], KnowledgeChoice]
    supplier_title_choices: dict[tuple[str, str], KnowledgeChoice]
    supplier_token_choices: dict[tuple[str, str], KnowledgeChoice]
    token_choices: dict[str, KnowledgeChoice]
