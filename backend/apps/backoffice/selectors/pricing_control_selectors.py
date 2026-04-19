from __future__ import annotations

from collections import deque
from decimal import Decimal

from django.db.models import Count

from apps.catalog.models import Category, Product
from apps.pricing.models import PricingPolicy, ProductPrice


def resolve_category_scope_ids(*, category_id: str, include_children: bool) -> list[str]:
    if not include_children:
        return [category_id]

    resolved: list[str] = []
    queue: deque[str] = deque([category_id])

    while queue:
        current_id = queue.popleft()
        if current_id in resolved:
            continue
        resolved.append(current_id)
        child_ids = list(Category.objects.filter(parent_id=current_id, is_active=True).values_list("id", flat=True))
        queue.extend(str(child_id) for child_id in child_ids)

    return resolved


def get_pricing_control_panel_payload() -> dict[str, object]:
    active_products = Product.objects.filter(is_active=True)
    active_prices = ProductPrice.objects.filter(product__is_active=True)

    global_policy = (
        PricingPolicy.objects.filter(scope=PricingPolicy.SCOPE_GLOBAL, is_active=True)
        .order_by("priority", "id")
        .first()
    )

    summary = {
        "products_total": active_products.count(),
        "priced_total": active_prices.count(),
        "featured_total": active_products.filter(is_featured=True).count(),
        "non_featured_total": active_products.filter(is_featured=False).count(),
        "category_policies_total": PricingPolicy.objects.filter(scope=PricingPolicy.SCOPE_CATEGORY, is_active=True).count(),
    }

    chart = {
        "markup_buckets": _build_markup_buckets(active_prices=active_prices),
        "policy_distribution": _build_policy_distribution(active_prices=active_prices),
    }

    return {
        "summary": summary,
        "global_policy": _serialize_policy(global_policy),
        "top_segment": {
            "supported": False,
            "reason": "missing_pricing_scope",
        },
        "chart": chart,
    }


def get_pricing_category_impact(*, category_id: str, include_children: bool) -> dict[str, object]:
    category_ids = resolve_category_scope_ids(category_id=category_id, include_children=include_children)
    affected_products = Product.objects.filter(is_active=True, category_id__in=category_ids).count()
    current_policy = (
        PricingPolicy.objects.filter(scope=PricingPolicy.SCOPE_CATEGORY, category_id=category_id, is_active=True)
        .order_by("priority", "id")
        .first()
    )
    current_percent_markup = str(current_policy.percent_markup) if current_policy else "0.00"

    category_rows = Category.objects.filter(id__in=category_ids).values("id", "name")
    category_names = {str(row["id"]): row["name"] for row in category_rows}

    return {
        "category_id": category_id,
        "include_children": include_children,
        "target_category_ids": category_ids,
        "target_categories": [
            {
                "id": target_id,
                "name": category_names.get(target_id, ""),
            }
            for target_id in category_ids
        ],
        "affected_products": affected_products,
        "current_percent_markup": current_percent_markup,
    }


def _serialize_policy(policy: PricingPolicy | None) -> dict[str, object] | None:
    if policy is None:
        return None
    return {
        "id": str(policy.id),
        "name": policy.name,
        "percent_markup": str(policy.percent_markup),
        "is_active": policy.is_active,
        "updated_at": policy.updated_at,
    }


def _build_markup_buckets(*, active_prices):
    grouped = list(
        active_prices.values("policy__scope", "policy__percent_markup")
        .annotate(total=Count("id"))
    )

    def normalize_percent(value: object | None) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value)).quantize(Decimal("0.01"))

    def format_percent_label(value: Decimal) -> str:
        normalized = format(value, "f").rstrip("0").rstrip(".")
        return f"{normalized}%"

    scope_labels = {
        PricingPolicy.SCOPE_GLOBAL: "Общая",
        PricingPolicy.SCOPE_CATEGORY: "Категория",
        PricingPolicy.SCOPE_BRAND: "Бренд",
        PricingPolicy.SCOPE_SUPPLIER: "Поставщик",
        PricingPolicy.SCOPE_BRAND_CATEGORY: "Бренд + категория",
    }
    scope_sort = {
        PricingPolicy.SCOPE_GLOBAL: 0,
        PricingPolicy.SCOPE_CATEGORY: 1,
        PricingPolicy.SCOPE_BRAND_CATEGORY: 2,
        PricingPolicy.SCOPE_BRAND: 3,
        PricingPolicy.SCOPE_SUPPLIER: 4,
    }

    percent_rows: list[dict[str, object]] = []
    no_policy_count = 0

    for item in grouped:
        scope = item["policy__scope"]
        percent_markup = normalize_percent(item["policy__percent_markup"])
        count = int(item["total"])
        if percent_markup is None:
            no_policy_count += count
            continue
        scope_key = str(scope or "unknown")
        key = f"{scope_key}_{format(percent_markup, 'f').replace('.', '_').replace('-', 'neg_')}"
        scope_label = scope_labels.get(scope_key, "Другая политика")
        percent_rows.append(
            {
                "key": key,
                "label": f"{format_percent_label(percent_markup)} · {scope_label}",
                "count": count,
                "_sort": percent_markup,
                "_scope_sort": scope_sort.get(scope_key, 99),
            }
        )

    percent_rows.sort(key=lambda row: (row["_scope_sort"], row["_sort"]))
    result = [{"key": row["key"], "label": row["label"], "count": row["count"]} for row in percent_rows]

    if no_policy_count:
        result.append({"key": "no_policy", "label": "Без политики", "count": no_policy_count})

    return result


def _build_policy_distribution(*, active_prices):
    grouped = list(
        active_prices.values("policy__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    top_groups = grouped[:5]
    remainder = sum(item["total"] for item in grouped[5:])
    items = [
        {
            "label": item["policy__name"] or "Без политики",
            "count": item["total"],
        }
        for item in top_groups
    ]
    if remainder:
        items.append({"label": "Остальные", "count": remainder})
    return items
