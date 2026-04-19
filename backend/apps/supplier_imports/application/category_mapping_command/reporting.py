from __future__ import annotations

from collections import Counter

from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services import CategoryMappingBulkStats

from .types import CommandOutput


def write_auto_map_started(
    output: CommandOutput,
    *,
    total: int,
    dry_run: bool,
    overwrite_manual: bool,
    force_map_all: bool,
    batch_size: int,
) -> None:
    output.write(
        f"Starting category auto-mapping for {total} rows "
        f"(dry_run={dry_run}, overwrite_manual={overwrite_manual}, force_map_all={force_map_all}, batch_size={batch_size})"
    )


def write_auto_map_progress(output: CommandOutput, *, index: int, total: int, stats: CategoryMappingBulkStats) -> None:
    output.write(
        f"[progress] {index}/{total} "
        f"updated={stats.updated} "
        f"auto={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)} "
        f"manual={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)} "
        f"review={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)} "
        f"unmapped={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)} "
        f"errors={stats.errors}"
    )


def write_auto_map_completed(
    output: CommandOutput,
    *,
    stats: CategoryMappingBulkStats,
    reason_counts: Counter[str],
    fallback_reason_counts: Counter[str],
    fallback_category_counts: Counter[str],
    category_names: dict[str, str],
) -> None:
    output.write_success("Category auto-mapping completed.")
    output.write(f"Processed: {stats.processed}")
    output.write(f"Updated: {stats.updated}")
    output.write(f"Skipped manual: {stats.skipped_manual}")
    output.write(f"Errors: {stats.errors}")
    output.write(f"auto_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)}")
    output.write(f"manual_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)}")
    output.write(f"needs_review: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)}")
    output.write(f"unmapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)}")

    if reason_counts:
        output.write("Top mapping reasons:")
        for reason, count in reason_counts.most_common(15):
            output.write(f"  - {reason}: {count}")

    if fallback_reason_counts:
        output.write("Top fallback reasons:")
        for reason, count in fallback_reason_counts.most_common(15):
            output.write(f"  - {reason}: {count}")

    if fallback_category_counts:
        output.write("Top fallback categories:")
        for category_id, count in fallback_category_counts.most_common(15):
            output.write(f"  - {category_names.get(category_id, category_id)} ({category_id}): {count}")

    if stats.unmapped_reason_counts:
        output.write("Top unmapped reasons:")
        for reason, count in sorted(stats.unmapped_reason_counts.items(), key=lambda item: item[1], reverse=True)[:10]:
            output.write(f"  - {reason}: {count}")


def write_risky_recheck_started(output: CommandOutput, *, total: int, dry_run: bool, batch_size: int) -> None:
    output.write(
        f"Starting risky mapping recheck for {total} rows "
        f"(dry_run={dry_run}, batch_size={batch_size})"
    )


def write_risky_recheck_progress(
    output: CommandOutput,
    *,
    index: int,
    total: int,
    stats: CategoryMappingBulkStats,
    post_status_counts: Counter[str],
) -> None:
    output.write(
        f"[progress] {index}/{total} "
        f"updated={stats.updated} "
        f"auto={post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)} "
        f"review={post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)} "
        f"unmapped={post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)} "
        f"errors={stats.errors}"
    )


def write_risky_recheck_completed(
    output: CommandOutput,
    *,
    stats: CategoryMappingBulkStats,
    downgraded_auto_to_review: int,
    corrected_categories: int,
    reason_changed: int,
    pre_status_counts: Counter[str],
    post_status_counts: Counter[str],
    transition_counts: Counter[str],
    pre_reason_counts: Counter[str],
    post_reason_counts: Counter[str],
    pre_category_counts: Counter[str],
    post_category_counts: Counter[str],
    category_id_to_name: dict[str, str],
) -> None:
    output.write_success("Risky mapping recheck completed.")
    output.write(f"Processed: {stats.processed}")
    output.write(f"Updated: {stats.updated}")
    output.write(f"Errors: {stats.errors}")
    output.write(f"auto->needs_review: {downgraded_auto_to_review}")
    output.write(f"category corrected: {corrected_categories}")
    output.write(f"reason changed: {reason_changed}")
    output.write(f"post auto_mapped: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)}")
    output.write(f"post needs_review: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)}")
    output.write(f"post manual_mapped: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)}")
    output.write(f"post unmapped: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)}")

    if pre_status_counts:
        output.write("Top statuses before:")
        for key, count in pre_status_counts.most_common(10):
            output.write(f"  - {key}: {count}")
    if post_status_counts:
        output.write("Top statuses after:")
        for key, count in post_status_counts.most_common(10):
            output.write(f"  - {key}: {count}")

    if transition_counts:
        output.write("Status transitions:")
        for key, count in transition_counts.most_common(10):
            output.write(f"  - {key}: {count}")

    if pre_reason_counts:
        output.write("Top reasons before:")
        for reason, count in pre_reason_counts.most_common(15):
            output.write(f"  - {reason}: {count}")
    if post_reason_counts:
        output.write("Top reasons after:")
        for reason, count in post_reason_counts.most_common(15):
            output.write(f"  - {reason}: {count}")

    if pre_category_counts:
        output.write("Top categories before:")
        for category_id, count in pre_category_counts.most_common(15):
            output.write(f"  - {category_id_to_name.get(category_id, category_id)} ({category_id}): {count}")
    if post_category_counts:
        output.write("Top categories after:")
        for category_id, count in post_category_counts.most_common(15):
            output.write(f"  - {category_id_to_name.get(category_id, category_id)} ({category_id}): {count}")


def write_selective_guardrail_started(
    output: CommandOutput,
    *,
    total: int,
    dry_run: bool,
    batch_size: int,
    guardrail_codes: tuple[str, ...],
) -> None:
    output.write(
        f"Starting selective guardrail recheck for {total} rows "
        f"(dry_run={dry_run}, batch_size={batch_size}, codes={list(guardrail_codes)})"
    )


def write_selective_guardrail_progress(output: CommandOutput, *, index: int, total: int, stats: CategoryMappingBulkStats) -> None:
    output.write(
        f"[progress] {index}/{total} "
        f"updated={stats.updated} "
        f"auto={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)} "
        f"review={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)} "
        f"errors={stats.errors}"
    )


def write_selective_guardrail_completed(
    output: CommandOutput,
    *,
    stats: CategoryMappingBulkStats,
    corrected_categories: int,
    auto_promoted: int,
    transition_counts: Counter[str],
    reason_counts: Counter[str],
) -> None:
    output.write_success("Selective guardrail recheck completed.")
    output.write(f"Processed: {stats.processed}")
    output.write(f"Updated: {stats.updated}")
    output.write(f"Errors: {stats.errors}")
    output.write(f"corrected categories: {corrected_categories}")
    output.write(f"promoted to auto_mapped: {auto_promoted}")
    output.write(f"post auto_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)}")
    output.write(f"post needs_review: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)}")
    output.write(f"post manual_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)}")
    output.write(f"post unmapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)}")

    if transition_counts:
        output.write("Status transitions:")
        for key, count in transition_counts.most_common(10):
            output.write(f"  - {key}: {count}")

    if reason_counts:
        output.write("Top reasons after selective recheck:")
        for key, count in reason_counts.most_common(15):
            output.write(f"  - {key}: {count}")
