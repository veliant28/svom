from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.commerce.models import LoyaltyPromoCode, LoyaltyPromoRedemption
from apps.pricing.services.rounding import quantize_money

User = get_user_model()


def search_loyalty_customers(*, query: str, limit: int = 25) -> list[dict[str, str]]:
    normalized = str(query or "").strip()
    qs = User.objects.filter(is_active=True).order_by("email")
    if normalized:
        qs = qs.filter(
            Q(email__icontains=normalized)
            | Q(first_name__icontains=normalized)
            | Q(last_name__icontains=normalized)
            | Q(phone__icontains=normalized)
        )

    items: list[dict[str, str]] = []
    for user in qs[: max(limit, 1)]:
        full_name = user.get_full_name().strip()
        items.append(
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": full_name,
                "label": full_name or user.email,
            }
        )
    return items


def list_recent_loyalty_issuances(*, limit: int = 25) -> list[LoyaltyPromoCode]:
    return list(
        LoyaltyPromoCode.objects.select_related("customer", "issued_by", "last_redeemed_order").order_by("-created_at")[: max(limit, 1)]
    )


def list_loyalty_staff_stats() -> list[dict[str, object]]:
    issued = (
        LoyaltyPromoCode.objects.exclude(issued_by__isnull=True)
        .values("issued_by_id", "issued_by__email", "issued_by__first_name", "issued_by__last_name")
        .annotate(
            issued_total=Count("id"),
            issued_delivery=Count("id", filter=Q(discount_type=LoyaltyPromoCode.DISCOUNT_DELIVERY_FEE)),
            issued_product=Count("id", filter=Q(discount_type=LoyaltyPromoCode.DISCOUNT_PRODUCT_MARKUP)),
            nominal_percent_total=Sum("discount_percent"),
            used_total=Count("id", filter=Q(usage_count__gt=0)),
        )
        .order_by("-issued_total", "issued_by__email")
    )

    staff_ids = [row["issued_by_id"] for row in issued if row.get("issued_by_id")]
    redemption_totals = {
        row["promo_code__issued_by_id"]: row["discount_sum"]
        for row in LoyaltyPromoRedemption.objects.filter(promo_code__issued_by_id__in=staff_ids)
        .values("promo_code__issued_by_id")
        .annotate(discount_sum=Sum("total_discount"))
    }

    rows: list[dict[str, object]] = []
    for row in issued:
        issued_total = int(row.get("issued_total") or 0)
        used_total = int(row.get("used_total") or 0)
        conversion_rate = Decimal("0")
        if issued_total > 0:
            conversion_rate = (Decimal(used_total) / Decimal(issued_total)) * Decimal("100")

        full_name = " ".join(
            [
                str(row.get("issued_by__first_name") or "").strip(),
                str(row.get("issued_by__last_name") or "").strip(),
            ]
        ).strip()
        rows.append(
            {
                "staff_id": str(row["issued_by_id"]),
                "staff_email": row.get("issued_by__email") or "",
                "staff_name": full_name,
                "issued_total": issued_total,
                "issued_delivery": int(row.get("issued_delivery") or 0),
                "issued_product": int(row.get("issued_product") or 0),
                "nominal_percent_total": str(Decimal(row.get("nominal_percent_total") or 0).quantize(Decimal("0.01"))),
                "discount_sum_total": str(quantize_money(Decimal(redemption_totals.get(row["issued_by_id"]) or 0))),
                "used_total": used_total,
                "conversion_rate": str(conversion_rate.quantize(Decimal("0.01"))),
            }
        )

    return rows


def list_loyalty_daily_issuance(*, days: int = 14) -> list[dict[str, object]]:
    safe_days = max(days, 1)
    today = timezone.localdate()
    day_from = today - timedelta(days=safe_days - 1)

    raw = (
        LoyaltyPromoCode.objects.filter(created_at__date__gte=day_from)
        .values("created_at__date")
        .annotate(total=Count("id"))
        .order_by("created_at__date")
    )
    raw_by_day = {str(row["created_at__date"]): int(row["total"]) for row in raw}

    rows: list[dict[str, object]] = []
    for index in range(safe_days):
        day = day_from + timedelta(days=index)
        key = str(day)
        rows.append(
            {
                "date": key,
                "total": raw_by_day.get(key, 0),
            }
        )
    return rows


def list_user_loyalty_codes(*, user) -> Sequence[LoyaltyPromoCode]:
    return list(
        LoyaltyPromoCode.objects.filter(customer=user)
        .select_related("issued_by", "last_redeemed_order")
        .order_by("-created_at")
    )
