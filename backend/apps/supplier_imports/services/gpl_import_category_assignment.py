from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Category
from apps.supplier_imports.services.gpl_category_mapping_audit import (
    STATUS_ACTIVE,
    STATUS_CONFLICT,
    STATUS_IGNORE,
    STATUS_MISSING,
    STATUS_REVIEW,
    CategoryDecision,
    CategoryTarget,
    GplCategoryMappingAuditor,
)

MAPPING_STATUS_ASSIGNED_GROUP = "assigned_by_group_mapping"
MAPPING_STATUS_ASSIGNED_ROW = "assigned_by_row_rule"
MAPPING_STATUS_NEEDS = "needs_category_mapping"
MAPPING_STATUS_MISSING = "missing_leaf_category"
MAPPING_STATUS_CONFLICT = "conflict"
MAPPING_STATUS_IGNORED = "ignored"


@dataclass(frozen=True)
class CategorySnapshot:
    category_id: str
    slug: str
    name: str
    parent_id: str
    is_assignable: bool
    root_name: str


@dataclass(frozen=True)
class GroupAssignmentDecision:
    mapping_status: str
    proposed_category_slug: str
    proposed_category_name: str
    proposed_root_name: str
    category_id: str
    category_is_assignable: bool
    matched_rule: str
    confidence: float
    reason: str
    invalid_target: bool
    non_assignable_target: bool
    missing_target: bool


@dataclass(frozen=True)
class RowAssignmentDecision:
    mapping_status: str
    proposed_category_slug: str
    proposed_category_name: str
    proposed_root_name: str
    category_id: str
    category_is_assignable: bool
    matched_rule: str
    confidence: float
    reason: str
    invalid_target: bool
    non_assignable_target: bool
    missing_target: bool


class GplImportCategoryAssignmentResolver:
    """Read-only category assignment resolver for GPL import preflight."""

    def __init__(self, *, auditor: GplCategoryMappingAuditor | None = None) -> None:
        self.auditor = auditor or GplCategoryMappingAuditor()
        self.categories_by_slug = self._load_categories_by_slug()

    def decide_group(self, *, rows: list[dict[str, str]]) -> GroupAssignmentDecision:
        decision = self.auditor.decide_group(rows=rows)
        return self._group_decision_from_auditor(decision=decision)

    def decide_row(
        self,
        *,
        row: dict[str, str],
        group_decision: GroupAssignmentDecision | None,
    ) -> RowAssignmentDecision:
        raw_category = str(row.get("Категорія") or row.get("category") or "").strip()
        raw_group = str(row.get("Група ТД") or row.get("group") or "").strip()
        brand = str(row.get("brand") or raw_group).strip()
        article = str(row.get("Артикул ТД") or row.get("Артикул") or row.get("article") or "").strip()
        name = str(row.get("Найменування") or row.get("name") or row.get("title") or "").strip()
        description = str(row.get("Опис") or row.get("description") or "").strip()

        if not any((raw_category, raw_group, brand, article, name, description)):
            return RowAssignmentDecision(
                mapping_status=MAPPING_STATUS_IGNORED,
                proposed_category_slug="",
                proposed_category_name="",
                proposed_root_name="",
                category_id="",
                category_is_assignable=False,
                matched_rule="",
                confidence=0.0,
                reason="empty_row",
                invalid_target=False,
                non_assignable_target=False,
                missing_target=False,
            )

        row_target = self.auditor.classify_row(row=row)
        if group_decision is not None and group_decision.mapping_status == MAPPING_STATUS_ASSIGNED_GROUP:
            if (
                row_target is not None
                and str(row_target.slug or "").strip()
                and str(row_target.slug or "").strip() != group_decision.proposed_category_slug
                and float(row_target.confidence or 0.0) >= 0.90
            ):
                validated = self._validate_target(
                    target_slug=str(row_target.slug or "").strip(),
                    confidence=float(row_target.confidence or 0.0),
                    matched_rule=str(row_target.reason or "").strip(),
                    fallback_reason="row_rule_overrides_group_mapping",
                    prefer_mapping_status=MAPPING_STATUS_ASSIGNED_ROW,
                )
                if validated is not None:
                    return validated

            return RowAssignmentDecision(
                mapping_status=MAPPING_STATUS_ASSIGNED_GROUP,
                proposed_category_slug=group_decision.proposed_category_slug,
                proposed_category_name=group_decision.proposed_category_name,
                proposed_root_name=group_decision.proposed_root_name,
                category_id=group_decision.category_id,
                category_is_assignable=group_decision.category_is_assignable,
                matched_rule=group_decision.matched_rule,
                confidence=group_decision.confidence,
                reason=group_decision.reason,
                invalid_target=False,
                non_assignable_target=False,
                missing_target=False,
            )

        if row_target is not None:
            validated = self._validate_target(
                target_slug=str(row_target.slug or "").strip(),
                confidence=float(row_target.confidence or 0.0),
                matched_rule=str(row_target.reason or "").strip(),
                fallback_reason="row_rule_target",
                prefer_mapping_status=MAPPING_STATUS_ASSIGNED_ROW,
            )
            if validated is not None:
                return validated

        if group_decision is not None and group_decision.mapping_status in {MAPPING_STATUS_MISSING, MAPPING_STATUS_CONFLICT, MAPPING_STATUS_IGNORED}:
            return RowAssignmentDecision(
                mapping_status=group_decision.mapping_status,
                proposed_category_slug=group_decision.proposed_category_slug,
                proposed_category_name=group_decision.proposed_category_name,
                proposed_root_name=group_decision.proposed_root_name,
                category_id=group_decision.category_id,
                category_is_assignable=group_decision.category_is_assignable,
                matched_rule=group_decision.matched_rule,
                confidence=group_decision.confidence,
                reason=group_decision.reason,
                invalid_target=group_decision.invalid_target,
                non_assignable_target=group_decision.non_assignable_target,
                missing_target=group_decision.missing_target,
            )

        return RowAssignmentDecision(
            mapping_status=MAPPING_STATUS_NEEDS,
            proposed_category_slug="",
            proposed_category_name="",
            proposed_root_name="",
            category_id="",
            category_is_assignable=False,
            matched_rule="",
            confidence=0.0,
            reason="no_confident_row_signal",
            invalid_target=False,
            non_assignable_target=False,
            missing_target=False,
        )

    def _group_decision_from_auditor(self, *, decision: CategoryDecision) -> GroupAssignmentDecision:
        if decision.status == STATUS_IGNORE:
            return GroupAssignmentDecision(
                mapping_status=MAPPING_STATUS_IGNORED,
                proposed_category_slug="",
                proposed_category_name="",
                proposed_root_name="",
                category_id="",
                category_is_assignable=False,
                matched_rule="",
                confidence=float(decision.confidence or 0.0),
                reason=str(decision.reason or "empty_group"),
                invalid_target=False,
                non_assignable_target=False,
                missing_target=False,
            )

        if decision.status == STATUS_ACTIVE:
            validated = self._validate_target(
                target_slug=str(decision.target_slug or "").strip(),
                confidence=float(decision.confidence or 0.0),
                matched_rule=str(decision.reason or "").strip(),
                fallback_reason="group_mapping_candidate",
                prefer_mapping_status=MAPPING_STATUS_ASSIGNED_GROUP,
            )
            if validated is not None:
                return GroupAssignmentDecision(
                    mapping_status=validated.mapping_status,
                    proposed_category_slug=validated.proposed_category_slug,
                    proposed_category_name=validated.proposed_category_name,
                    proposed_root_name=validated.proposed_root_name,
                    category_id=validated.category_id,
                    category_is_assignable=validated.category_is_assignable,
                    matched_rule=validated.matched_rule,
                    confidence=validated.confidence,
                    reason=validated.reason,
                    invalid_target=validated.invalid_target,
                    non_assignable_target=validated.non_assignable_target,
                    missing_target=validated.missing_target,
                )

        mapping_status = MAPPING_STATUS_NEEDS
        if decision.status == STATUS_MISSING:
            mapping_status = MAPPING_STATUS_MISSING
        elif decision.status == STATUS_CONFLICT:
            mapping_status = MAPPING_STATUS_CONFLICT
        elif decision.status == STATUS_REVIEW:
            mapping_status = MAPPING_STATUS_NEEDS

        return GroupAssignmentDecision(
            mapping_status=mapping_status,
            proposed_category_slug=str(decision.target_slug or "").strip(),
            proposed_category_name=str(decision.target_name or "").strip(),
            proposed_root_name=str(decision.root_name or "").strip(),
            category_id="",
            category_is_assignable=False,
            matched_rule="",
            confidence=float(decision.confidence or 0.0),
            reason=str(decision.reason or "group_not_mapped"),
            invalid_target=False,
            non_assignable_target=False,
            missing_target=(mapping_status == MAPPING_STATUS_MISSING),
        )

    def _validate_target(
        self,
        *,
        target_slug: str,
        confidence: float,
        matched_rule: str,
        fallback_reason: str,
        prefer_mapping_status: str,
    ) -> RowAssignmentDecision | None:
        slug = str(target_slug or "").strip()
        if not slug:
            return None

        category = self.categories_by_slug.get(slug)
        if category is None:
            return RowAssignmentDecision(
                mapping_status=MAPPING_STATUS_MISSING,
                proposed_category_slug=slug,
                proposed_category_name="",
                proposed_root_name="",
                category_id="",
                category_is_assignable=False,
                matched_rule=matched_rule,
                confidence=confidence,
                reason="target_slug_missing",
                invalid_target=False,
                non_assignable_target=False,
                missing_target=True,
            )

        category_id = str(category.category_id)
        if not category.parent_id:
            return RowAssignmentDecision(
                mapping_status=MAPPING_STATUS_CONFLICT,
                proposed_category_slug=slug,
                proposed_category_name=category.name,
                proposed_root_name=category.root_name,
                category_id=category_id,
                category_is_assignable=bool(category.is_assignable),
                matched_rule=matched_rule,
                confidence=confidence,
                reason="target_root_forbidden",
                invalid_target=True,
                non_assignable_target=False,
                missing_target=False,
            )

        if not category.is_assignable:
            return RowAssignmentDecision(
                mapping_status=MAPPING_STATUS_CONFLICT,
                proposed_category_slug=slug,
                proposed_category_name=category.name,
                proposed_root_name=category.root_name,
                category_id=category_id,
                category_is_assignable=False,
                matched_rule=matched_rule,
                confidence=confidence,
                reason="target_non_assignable_forbidden",
                invalid_target=False,
                non_assignable_target=True,
                missing_target=False,
            )

        return RowAssignmentDecision(
            mapping_status=prefer_mapping_status,
            proposed_category_slug=slug,
            proposed_category_name=category.name,
            proposed_root_name=category.root_name,
            category_id=category_id,
            category_is_assignable=True,
            matched_rule=matched_rule,
            confidence=confidence,
            reason=fallback_reason,
            invalid_target=False,
            non_assignable_target=False,
            missing_target=False,
        )

    @staticmethod
    def _load_categories_by_slug() -> dict[str, CategorySnapshot]:
        rows = list(
            Category.objects.filter(is_active=True).only("id", "slug", "name", "parent_id", "is_assignable")
        )
        by_id = {str(item.id): item for item in rows}

        root_cache: dict[str, str] = {}

        def root_name_for(category: Category) -> str:
            category_id = str(category.id)
            cached = root_cache.get(category_id)
            if cached is not None:
                return cached

            current = category
            safety = 0
            while current.parent_id and safety < 32:
                parent = by_id.get(str(current.parent_id))
                if parent is None:
                    break
                current = parent
                safety += 1

            root_name = str(current.name or "")
            root_cache[category_id] = root_name
            return root_name

        out: dict[str, CategorySnapshot] = {}
        for item in rows:
            slug = str(item.slug or "").strip()
            if not slug:
                continue
            out[slug] = CategorySnapshot(
                category_id=str(item.id),
                slug=slug,
                name=str(item.name or ""),
                parent_id=str(item.parent_id or ""),
                is_assignable=bool(item.is_assignable),
                root_name=root_name_for(item),
            )
        return out


__all__ = [
    "GplImportCategoryAssignmentResolver",
    "GroupAssignmentDecision",
    "RowAssignmentDecision",
    "MAPPING_STATUS_ASSIGNED_GROUP",
    "MAPPING_STATUS_ASSIGNED_ROW",
    "MAPPING_STATUS_NEEDS",
    "MAPPING_STATUS_MISSING",
    "MAPPING_STATUS_CONFLICT",
    "MAPPING_STATUS_IGNORED",
]
