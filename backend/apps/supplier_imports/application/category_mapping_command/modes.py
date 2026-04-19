from __future__ import annotations

from collections import Counter

from django.db.models import QuerySet

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services import CategoryMappingBulkStats, SupplierRawOfferCategoryMappingService

from . import prefilters, reporting
from .types import CategoryMappingCommandOptions, CommandOutput


def run_auto_map(
    *,
    queryset: QuerySet[SupplierRawOffer],
    options: CategoryMappingCommandOptions,
    output: CommandOutput,
) -> None:
    queryset, total = prefilters.apply_limit(queryset=queryset, limit=options.limit)
    if total == 0:
        output.write_warning("No supplier raw offers selected.")
        return

    reporting.write_auto_map_started(
        output,
        total=total,
        dry_run=options.dry_run,
        overwrite_manual=options.overwrite_manual,
        force_map_all=options.force_map_all,
        batch_size=options.batch_size,
    )

    service = SupplierRawOfferCategoryMappingService()
    stats = CategoryMappingBulkStats()
    reason_counts: Counter[str] = Counter()
    fallback_reason_counts: Counter[str] = Counter()
    fallback_category_counts: Counter[str] = Counter()

    for index, raw_offer in enumerate(queryset.iterator(chunk_size=options.batch_size), start=1):
        stats.processed += 1
        try:
            result = service.apply_auto_mapping(
                raw_offer=raw_offer,
                overwrite_manual=options.overwrite_manual,
                force_map_all=options.force_map_all,
                dry_run=options.dry_run,
            )
        except Exception:
            stats.errors += 1
            continue

        if result.skipped_manual:
            stats.skipped_manual += 1
        if result.updated:
            stats.updated += 1
        stats.bump_status(result.status)

        reason_key = result.reason or "no_reason"
        reason_counts[reason_key] += 1
        if reason_key.startswith("force_"):
            fallback_reason_counts[reason_key] += 1
            if result.category_id:
                fallback_category_counts[result.category_id] += 1
        if result.status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED:
            stats.bump_unmapped_reason(result.reason)

        if index <= 5 or index % 1000 == 0 or index == total:
            reporting.write_auto_map_progress(output, index=index, total=total, stats=stats)

    category_names: dict[str, str] = {}
    if fallback_category_counts:
        category_names = {
            str(item.id): item.name
            for item in Category.objects.filter(id__in=list(fallback_category_counts.keys()))
        }

    reporting.write_auto_map_completed(
        output,
        stats=stats,
        reason_counts=reason_counts,
        fallback_reason_counts=fallback_reason_counts,
        fallback_category_counts=fallback_category_counts,
        category_names=category_names,
    )


def run_risky_recheck(
    *,
    queryset: QuerySet[SupplierRawOffer],
    options: CategoryMappingCommandOptions,
    output: CommandOutput,
) -> None:
    queryset = prefilters.apply_risky_recheck_queryset(queryset)
    queryset, total = prefilters.apply_limit(queryset=queryset, limit=options.limit)

    if total == 0:
        output.write_warning("No risky mapped rows selected for recheck.")
        return

    reporting.write_risky_recheck_started(
        output,
        total=total,
        dry_run=options.dry_run,
        batch_size=options.batch_size,
    )

    service = SupplierRawOfferCategoryMappingService()
    stats = CategoryMappingBulkStats()
    pre_reason_counts: Counter[str] = Counter()
    post_reason_counts: Counter[str] = Counter()
    pre_category_counts: Counter[str] = Counter()
    post_category_counts: Counter[str] = Counter()
    pre_status_counts: Counter[str] = Counter()
    post_status_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()

    category_id_to_name: dict[str, str] = {}
    corrected_categories = 0
    downgraded_auto_to_review = 0
    reason_changed = 0

    for index, raw_offer in enumerate(queryset.iterator(chunk_size=options.batch_size), start=1):
        old_status = raw_offer.category_mapping_status
        old_reason = raw_offer.category_mapping_reason or "no_reason"
        old_category_id = str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else ""
        old_category_name = (
            raw_offer.mapped_category.name if raw_offer.mapped_category_id and raw_offer.mapped_category else old_category_id
        )
        if old_category_id:
            category_id_to_name[old_category_id] = old_category_name

        pre_reason_counts[old_reason] += 1
        pre_status_counts[old_status] += 1
        if old_category_id:
            pre_category_counts[old_category_id] += 1

        stats.processed += 1
        try:
            result = service.recheck_risky_mapping(raw_offer=raw_offer, dry_run=options.dry_run)
        except Exception:
            stats.errors += 1
            continue

        if result.skipped_manual:
            stats.skipped_manual += 1
        if result.updated:
            stats.updated += 1

        stats.bump_status(result.status)
        post_reason = result.reason or "no_reason"
        post_reason_counts[post_reason] += 1
        post_status_counts[result.status] += 1
        if result.category_id:
            post_category_counts[result.category_id] += 1

        transition_counts[f"{old_status}->{result.status}"] += 1

        if old_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED and result.status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW:
            downgraded_auto_to_review += 1
        if old_category_id and result.category_id and old_category_id != result.category_id:
            corrected_categories += 1
        if old_reason != post_reason:
            reason_changed += 1

        if index <= 5 or index % 1000 == 0 or index == total:
            reporting.write_risky_recheck_progress(
                output,
                index=index,
                total=total,
                stats=stats,
                post_status_counts=post_status_counts,
            )

    if post_category_counts:
        missing_ids = [item for item in post_category_counts.keys() if item not in category_id_to_name]
        if missing_ids:
            for row in Category.objects.filter(id__in=missing_ids).only("id", "name"):
                category_id_to_name[str(row.id)] = row.name

    reporting.write_risky_recheck_completed(
        output,
        stats=stats,
        downgraded_auto_to_review=downgraded_auto_to_review,
        corrected_categories=corrected_categories,
        reason_changed=reason_changed,
        pre_status_counts=pre_status_counts,
        post_status_counts=post_status_counts,
        transition_counts=transition_counts,
        pre_reason_counts=pre_reason_counts,
        post_reason_counts=post_reason_counts,
        pre_category_counts=pre_category_counts,
        post_category_counts=post_category_counts,
        category_id_to_name=category_id_to_name,
    )


def run_selective_guardrail_recheck(
    *,
    queryset: QuerySet[SupplierRawOffer],
    options: CategoryMappingCommandOptions,
    output: CommandOutput,
) -> None:
    queryset = prefilters.apply_selective_guardrail_queryset(
        queryset=queryset,
        guardrail_codes=options.recheck_guardrail_codes,
        reasons=options.recheck_reasons,
        category_name_filters=options.recheck_category_names,
        title_patterns=options.recheck_title_patterns,
    )
    queryset, total = prefilters.apply_limit(queryset=queryset, limit=options.limit)

    if total == 0:
        output.write_warning("No rows selected for selective guardrail recheck.")
        return

    reporting.write_selective_guardrail_started(
        output,
        total=total,
        dry_run=options.dry_run,
        batch_size=options.batch_size,
        guardrail_codes=options.recheck_guardrail_codes,
    )

    service = SupplierRawOfferCategoryMappingService()
    stats = CategoryMappingBulkStats()
    transition_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    corrected_categories = 0
    auto_promoted = 0

    allowed_codes = set(options.recheck_guardrail_codes) if options.recheck_guardrail_codes else None
    for index, raw_offer in enumerate(queryset.iterator(chunk_size=options.batch_size), start=1):
        old_status = raw_offer.category_mapping_status
        old_category_id = str(raw_offer.mapped_category_id or "")

        stats.processed += 1
        try:
            result = service.recheck_guardrail_mapping(
                raw_offer=raw_offer,
                allowed_guardrail_codes=allowed_codes,
                dry_run=options.dry_run,
            )
        except Exception:
            stats.errors += 1
            continue

        if result.skipped_manual:
            stats.skipped_manual += 1
        if result.updated:
            stats.updated += 1
        stats.bump_status(result.status)
        reason_counts[result.reason or "no_reason"] += 1
        transition_counts[f"{old_status}->{result.status}"] += 1

        if old_category_id and result.category_id and old_category_id != result.category_id:
            corrected_categories += 1
        if old_status != SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED and result.status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED:
            auto_promoted += 1

        if index <= 5 or index % 1000 == 0 or index == total:
            reporting.write_selective_guardrail_progress(output, index=index, total=total, stats=stats)

    reporting.write_selective_guardrail_completed(
        output,
        stats=stats,
        corrected_categories=corrected_categories,
        auto_promoted=auto_promoted,
        transition_counts=transition_counts,
        reason_counts=reason_counts,
    )
