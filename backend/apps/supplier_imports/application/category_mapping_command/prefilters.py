from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.supplier_imports.models import SupplierRawOffer

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


def build_base_queryset(*, supplier_codes: tuple[str, ...]) -> QuerySet[SupplierRawOffer]:
    queryset = SupplierRawOffer.objects.select_related(
        "supplier",
        "matched_product",
        "matched_product__category",
        "mapped_category",
    ).order_by("created_at")

    if supplier_codes:
        queryset = queryset.filter(supplier__code__in=supplier_codes)
    return queryset


def apply_limit(*, queryset: QuerySet[SupplierRawOffer], limit: int | None) -> tuple[QuerySet[SupplierRawOffer], int]:
    if limit and limit > 0:
        selected_ids = list(queryset.values_list("id", flat=True)[:limit])
        queryset = queryset.filter(id__in=selected_ids).order_by("created_at")
        return queryset, len(selected_ids)
    return queryset, queryset.count()


def apply_risky_recheck_queryset(queryset: QuerySet[SupplierRawOffer]) -> QuerySet[SupplierRawOffer]:
    return (
        queryset.filter(mapped_category_id__isnull=False)
        .exclude(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED)
        .filter(category_mapping_reason__in=RISKY_FORCED_REASONS)
        .filter(
            Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
            | Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW)
        )
    )


def apply_selective_guardrail_queryset(
    *,
    queryset: QuerySet[SupplierRawOffer],
    guardrail_codes: tuple[str, ...],
    reasons: tuple[str, ...],
    category_name_filters: tuple[str, ...],
    title_patterns: tuple[str, ...],
) -> QuerySet[SupplierRawOffer]:
    queryset = (
        queryset.filter(mapped_category_id__isnull=False)
        .exclude(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED)
        .filter(
            Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED)
            | Q(category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW)
        )
    )

    if guardrail_codes:
        queryset = queryset.filter(build_guardrail_prefilter_q(guardrail_codes))
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

    return queryset


def build_guardrail_prefilter_q(guardrail_codes: tuple[str, ...]) -> Q:
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
