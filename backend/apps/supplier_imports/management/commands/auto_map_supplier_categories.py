from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services import CategoryMappingBulkStats, SupplierRawOfferCategoryMappingService

RISKY_FORCED_REASONS = (
    SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE,
    SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER,
    SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER,
    SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME,
    SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT,
    SupplierRawOffer.CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT,
)
SELECTIVE_GUARDRAIL_CODES = (
    "cabin_filter_vs_air_filter",
    "hub_bearing_vs_gearbox_bearing",
    "hub_bearing_vs_cv_joint",
    "hub_bearing_vs_shock",
    "brake_pads_vs_injector",
    "brake_pads_vs_shock",
    "brake_pads_vs_caliper_repair",
)
_AIR_FILTER_TOKEN_Q = (
    Q(product_name__icontains="повітряний фільтр")
    | Q(product_name__icontains="фильтр воздуш")
    | Q(product_name__icontains="air filter")
    | Q(product_name__icontains="фільтр двигун")
    | Q(product_name__icontains="фильтр двигателя")
    | Q(product_name__icontains="engine air")
    | Q(product_name__icontains="intake")
)
_GEARBOX_TOKEN_Q = (
    Q(product_name__icontains="кпп")
    | Q(product_name__icontains="коробк")
    | Q(product_name__icontains="мкпп")
    | Q(product_name__icontains="акпп")
    | Q(product_name__icontains="transmission")
    | Q(product_name__icontains="gearbox")
    | Q(product_name__icontains="трансмис")
    | Q(product_name__icontains="ремкомплект кпп")
)


class Command(BaseCommand):
    help = "Auto-map supplier raw offers to catalog categories with conservative confidence thresholds."

    def add_arguments(self, parser):
        parser.add_argument(
            "--supplier",
            action="append",
            default=None,
            help="Supplier code filter. Can be passed multiple times.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Iterator chunk size.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional limit for processed rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate mapping without saving DB updates.",
        )
        parser.add_argument(
            "--overwrite-manual",
            action="store_true",
            help="Allow overwriting rows with manual_mapped status.",
        )
        parser.add_argument(
            "--force-map-all",
            action="store_true",
            help="Mandatory fallback mode: assign category to every row; low-confidence rows become needs_review.",
        )
        parser.add_argument(
            "--recheck-risky-mappings",
            action="store_true",
            help="Re-check already mapped risky forced rows and downgrade/fix suspicious mappings without creating unmapped rows.",
        )
        parser.add_argument(
            "--recheck-guardrail-codes",
            action="append",
            default=None,
            choices=SELECTIVE_GUARDRAIL_CODES,
            help="Selective guardrail recheck by guardrail code. Can be passed multiple times.",
        )
        parser.add_argument(
            "--recheck-reason",
            action="append",
            default=None,
            help="Optional reason filters for selective recheck. Can be passed multiple times.",
        )
        parser.add_argument(
            "--recheck-category-name",
            action="append",
            default=None,
            help="Optional mapped category name contains filters for selective recheck.",
        )
        parser.add_argument(
            "--recheck-title-pattern",
            action="append",
            default=None,
            help="Optional product_name contains filters for selective recheck.",
        )

    def handle(self, *args, **options):
        supplier_codes = [str(item).strip().lower() for item in (options.get("supplier") or []) if str(item).strip()]
        batch_size = max(50, int(options.get("batch_size") or 500))
        limit = options.get("limit")
        dry_run = bool(options.get("dry_run"))
        overwrite_manual = bool(options.get("overwrite_manual"))
        force_map_all = bool(options.get("force_map_all"))
        recheck_risky_mappings = bool(options.get("recheck_risky_mappings"))
        recheck_guardrail_codes = tuple(str(item).strip() for item in (options.get("recheck_guardrail_codes") or []) if str(item).strip())
        recheck_reasons = tuple(str(item).strip() for item in (options.get("recheck_reason") or []) if str(item).strip())
        recheck_category_names = tuple(str(item).strip() for item in (options.get("recheck_category_name") or []) if str(item).strip())
        recheck_title_patterns = tuple(str(item).strip() for item in (options.get("recheck_title_pattern") or []) if str(item).strip())

        queryset = SupplierRawOffer.objects.select_related(
            "supplier",
            "matched_product",
            "matched_product__category",
            "mapped_category",
        ).order_by("created_at")

        if supplier_codes:
            queryset = queryset.filter(supplier__code__in=supplier_codes)

        if recheck_risky_mappings:
            self._run_recheck(
                queryset=queryset,
                batch_size=batch_size,
                limit=limit,
                dry_run=dry_run,
            )
            return
        if recheck_guardrail_codes or recheck_reasons or recheck_category_names or recheck_title_patterns:
            self._run_selective_guardrail_recheck(
                queryset=queryset,
                batch_size=batch_size,
                limit=limit,
                dry_run=dry_run,
                guardrail_codes=recheck_guardrail_codes,
                reasons=recheck_reasons,
                category_name_filters=recheck_category_names,
                title_patterns=recheck_title_patterns,
            )
            return

        if limit and limit > 0:
            selected_ids = list(queryset.values_list("id", flat=True)[:limit])
            queryset = queryset.filter(id__in=selected_ids).order_by("created_at")
            total = len(selected_ids)
        else:
            total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No supplier raw offers selected."))
            return

        self.stdout.write(
            f"Starting category auto-mapping for {total} rows "
            f"(dry_run={dry_run}, overwrite_manual={overwrite_manual}, force_map_all={force_map_all}, batch_size={batch_size})"
        )

        service = SupplierRawOfferCategoryMappingService()
        stats = CategoryMappingBulkStats()
        reason_counts: Counter[str] = Counter()
        fallback_reason_counts: Counter[str] = Counter()
        fallback_category_counts: Counter[str] = Counter()

        for index, raw_offer in enumerate(queryset.iterator(chunk_size=batch_size), start=1):
            stats.processed += 1
            try:
                result = service.apply_auto_mapping(
                    raw_offer=raw_offer,
                    overwrite_manual=overwrite_manual,
                    force_map_all=force_map_all,
                    dry_run=dry_run,
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
                self.stdout.write(
                    f"[progress] {index}/{total} "
                    f"updated={stats.updated} "
                    f"auto={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)} "
                    f"manual={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)} "
                    f"review={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)} "
                    f"unmapped={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)} "
                    f"errors={stats.errors}"
                )

        self.stdout.write(self.style.SUCCESS("Category auto-mapping completed."))
        self.stdout.write(f"Processed: {stats.processed}")
        self.stdout.write(f"Updated: {stats.updated}")
        self.stdout.write(f"Skipped manual: {stats.skipped_manual}")
        self.stdout.write(f"Errors: {stats.errors}")
        self.stdout.write(f"auto_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)}")
        self.stdout.write(f"manual_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)}")
        self.stdout.write(f"needs_review: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)}")
        self.stdout.write(f"unmapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)}")

        if reason_counts:
            self.stdout.write("Top mapping reasons:")
            for reason, count in reason_counts.most_common(15):
                self.stdout.write(f"  - {reason}: {count}")

        if fallback_reason_counts:
            self.stdout.write("Top fallback reasons:")
            for reason, count in fallback_reason_counts.most_common(15):
                self.stdout.write(f"  - {reason}: {count}")

        if fallback_category_counts:
            self.stdout.write("Top fallback categories:")
            category_names = {
                str(item.id): item.name
                for item in Category.objects.filter(id__in=list(fallback_category_counts.keys()))
            }
            for category_id, count in fallback_category_counts.most_common(15):
                self.stdout.write(f"  - {category_names.get(category_id, category_id)} ({category_id}): {count}")

        if stats.unmapped_reason_counts:
            self.stdout.write("Top unmapped reasons:")
            for reason, count in sorted(stats.unmapped_reason_counts.items(), key=lambda item: item[1], reverse=True)[:10]:
                self.stdout.write(f"  - {reason}: {count}")

    def _run_recheck(self, *, queryset, batch_size: int, limit: int | None, dry_run: bool) -> None:
        queryset = queryset.filter(
            mapped_category_id__isnull=False,
        ).exclude(
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        ).filter(
            category_mapping_reason__in=RISKY_FORCED_REASONS,
        ).filter(
            Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
            | Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW)
        )

        if limit and limit > 0:
            selected_ids = list(queryset.values_list("id", flat=True)[:limit])
            queryset = queryset.filter(id__in=selected_ids).order_by("created_at")
            total = len(selected_ids)
        else:
            total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No risky mapped rows selected for recheck."))
            return

        self.stdout.write(
            f"Starting risky mapping recheck for {total} rows "
            f"(dry_run={dry_run}, batch_size={batch_size})"
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

        for index, raw_offer in enumerate(queryset.iterator(chunk_size=batch_size), start=1):
            old_status = raw_offer.category_mapping_status
            old_reason = raw_offer.category_mapping_reason or "no_reason"
            old_category_id = str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else ""
            old_category_name = raw_offer.mapped_category.name if raw_offer.mapped_category_id and raw_offer.mapped_category else old_category_id
            if old_category_id:
                category_id_to_name[old_category_id] = old_category_name

            pre_reason_counts[old_reason] += 1
            pre_status_counts[old_status] += 1
            if old_category_id:
                pre_category_counts[old_category_id] += 1

            stats.processed += 1
            try:
                result = service.recheck_risky_mapping(raw_offer=raw_offer, dry_run=dry_run)
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
                self.stdout.write(
                    f"[progress] {index}/{total} "
                    f"updated={stats.updated} "
                    f"auto={post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)} "
                    f"review={post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)} "
                    f"unmapped={post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)} "
                    f"errors={stats.errors}"
                )

        if post_category_counts:
            missing_ids = [item for item in post_category_counts.keys() if item not in category_id_to_name]
            if missing_ids:
                for row in Category.objects.filter(id__in=missing_ids).only("id", "name"):
                    category_id_to_name[str(row.id)] = row.name

        self.stdout.write(self.style.SUCCESS("Risky mapping recheck completed."))
        self.stdout.write(f"Processed: {stats.processed}")
        self.stdout.write(f"Updated: {stats.updated}")
        self.stdout.write(f"Errors: {stats.errors}")
        self.stdout.write(f"auto->needs_review: {downgraded_auto_to_review}")
        self.stdout.write(f"category corrected: {corrected_categories}")
        self.stdout.write(f"reason changed: {reason_changed}")
        self.stdout.write(f"post auto_mapped: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)}")
        self.stdout.write(f"post needs_review: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)}")
        self.stdout.write(f"post manual_mapped: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)}")
        self.stdout.write(f"post unmapped: {post_status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)}")

        if pre_status_counts:
            self.stdout.write("Top statuses before:")
            for key, count in pre_status_counts.most_common(10):
                self.stdout.write(f"  - {key}: {count}")
        if post_status_counts:
            self.stdout.write("Top statuses after:")
            for key, count in post_status_counts.most_common(10):
                self.stdout.write(f"  - {key}: {count}")

        if transition_counts:
            self.stdout.write("Status transitions:")
            for key, count in transition_counts.most_common(10):
                self.stdout.write(f"  - {key}: {count}")

        if pre_reason_counts:
            self.stdout.write("Top reasons before:")
            for reason, count in pre_reason_counts.most_common(15):
                self.stdout.write(f"  - {reason}: {count}")
        if post_reason_counts:
            self.stdout.write("Top reasons after:")
            for reason, count in post_reason_counts.most_common(15):
                self.stdout.write(f"  - {reason}: {count}")

        if pre_category_counts:
            self.stdout.write("Top categories before:")
            for category_id, count in pre_category_counts.most_common(15):
                category_name = category_id_to_name.get(category_id, category_id)
                self.stdout.write(f"  - {category_name} ({category_id}): {count}")
        if post_category_counts:
            self.stdout.write("Top categories after:")
            for category_id, count in post_category_counts.most_common(15):
                category_name = category_id_to_name.get(category_id, category_id)
                self.stdout.write(f"  - {category_name} ({category_id}): {count}")

    def _run_selective_guardrail_recheck(
        self,
        *,
        queryset,
        batch_size: int,
        limit: int | None,
        dry_run: bool,
        guardrail_codes: tuple[str, ...],
        reasons: tuple[str, ...],
        category_name_filters: tuple[str, ...],
        title_patterns: tuple[str, ...],
    ) -> None:
        queryset = queryset.filter(
            mapped_category_id__isnull=False,
        ).exclude(
            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        ).filter(
            Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
            | Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW)
        )

        if guardrail_codes:
            queryset = queryset.filter(self._build_guardrail_prefilter_q(guardrail_codes))
        if reasons:
            queryset = queryset.filter(category_mapping_reason__in=reasons)
        if category_name_filters:
            category_q = Q()
            for value in category_name_filters:
                category_q |= Q(mapped_category__name__icontains=value)
            queryset = queryset.filter(category_q)
        if title_patterns:
            title_q = Q()
            for value in title_patterns:
                title_q |= Q(product_name__icontains=value)
            queryset = queryset.filter(title_q)

        if limit and limit > 0:
            selected_ids = list(queryset.values_list("id", flat=True)[:limit])
            queryset = queryset.filter(id__in=selected_ids).order_by("created_at")
            total = len(selected_ids)
        else:
            total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No rows selected for selective guardrail recheck."))
            return

        self.stdout.write(
            f"Starting selective guardrail recheck for {total} rows "
            f"(dry_run={dry_run}, batch_size={batch_size}, codes={list(guardrail_codes)})"
        )

        service = SupplierRawOfferCategoryMappingService()
        stats = CategoryMappingBulkStats()
        transition_counts: Counter[str] = Counter()
        reason_counts: Counter[str] = Counter()
        corrected_categories = 0
        auto_promoted = 0

        allowed_codes = set(guardrail_codes) if guardrail_codes else None
        for index, raw_offer in enumerate(queryset.iterator(chunk_size=batch_size), start=1):
            old_status = raw_offer.category_mapping_status
            old_category_id = str(raw_offer.mapped_category_id or "")

            stats.processed += 1
            try:
                result = service.recheck_guardrail_mapping(
                    raw_offer=raw_offer,
                    allowed_guardrail_codes=allowed_codes,
                    dry_run=dry_run,
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
                self.stdout.write(
                    f"[progress] {index}/{total} "
                    f"updated={stats.updated} "
                    f"auto={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)} "
                    f"review={stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)} "
                    f"errors={stats.errors}"
                )

        self.stdout.write(self.style.SUCCESS("Selective guardrail recheck completed."))
        self.stdout.write(f"Processed: {stats.processed}")
        self.stdout.write(f"Updated: {stats.updated}")
        self.stdout.write(f"Errors: {stats.errors}")
        self.stdout.write(f"corrected categories: {corrected_categories}")
        self.stdout.write(f"promoted to auto_mapped: {auto_promoted}")
        self.stdout.write(f"post auto_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED, 0)}")
        self.stdout.write(f"post needs_review: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, 0)}")
        self.stdout.write(f"post manual_mapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, 0)}")
        self.stdout.write(f"post unmapped: {stats.status_counts.get(SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED, 0)}")
        if transition_counts:
            self.stdout.write("Status transitions:")
            for key, count in transition_counts.most_common(10):
                self.stdout.write(f"  - {key}: {count}")
        if reason_counts:
            self.stdout.write("Top reasons after selective recheck:")
            for key, count in reason_counts.most_common(15):
                self.stdout.write(f"  - {key}: {count}")

    def _build_guardrail_prefilter_q(self, guardrail_codes: tuple[str, ...]) -> Q:
        predicate = Q(pk__isnull=True)
        if "cabin_filter_vs_air_filter" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Фільтр салону") & _AIR_FILTER_TOKEN_Q
        if "hub_bearing_vs_gearbox_bearing" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Підшипник маточини") & _GEARBOX_TOKEN_Q
        if "hub_bearing_vs_cv_joint" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Підшипник маточини") & (
                Q(product_name__icontains="шрус")
                | Q(product_name__icontains="шркш")
                | Q(product_name__icontains="гранат")
                | Q(product_name__icontains="пильник")
                | Q(product_name__icontains="пыльник")
            )
        if "hub_bearing_vs_shock" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Підшипник маточини") & (
                Q(product_name__icontains="амортиз")
                | Q(product_name__icontains="стойк")
                | Q(product_name__icontains="опора амортиз")
            )
        if "brake_pads_vs_injector" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Гальмівні колодки") & (
                Q(product_name__icontains="форсун")
                | Q(product_name__icontains="injector")
                | Q(product_name__icontains="nozzle")
            )
        if "brake_pads_vs_shock" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Гальмівні колодки") & (
                Q(product_name__icontains="амортиз")
                | Q(product_name__icontains="стойк")
                | Q(product_name__icontains="опора амортиз")
            )
        if "brake_pads_vs_caliper_repair" in guardrail_codes:
            predicate |= Q(mapped_category__name__icontains="Гальмівні колодки") & Q(product_name__icontains="супорт") & (
                Q(product_name__icontains="пружин")
                | Q(product_name__icontains="ремкомплект")
                | Q(product_name__icontains="р/к")
            )
        return predicate
