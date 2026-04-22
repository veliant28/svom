from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from apps.commerce.models import LoyaltyPromoCode, LoyaltyPromoRedemption, OrderNovaPoshtaWaybillEvent
from apps.pricing.models import PriceHistory
from apps.pricing.services.rounding import quantize_money


User = get_user_model()

SUPPORTED_STAFF_ROLES = {"manager", "operator"}


def build_backoffice_staff_activity_payload(*, role: str, days: int = 14) -> dict:
    normalized_role = str(role or "").strip().lower()
    if normalized_role not in SUPPORTED_STAFF_ROLES:
        raise ValueError("Unsupported staff role.")

    safe_days = max(1, min(int(days or 14), 90))
    now = timezone.now()
    day_from = timezone.localdate() - timedelta(days=safe_days - 1)
    role_group_name = f"Backoffice Role: {normalized_role}"

    staff_rows = list(
        User.objects.filter(is_active=True, is_staff=True, groups__name=role_group_name)
        .order_by("first_name", "last_name", "email")
        .values("id", "email", "first_name", "last_name")
        .distinct()
    )
    staff_ids = [row["id"] for row in staff_rows]

    if not staff_ids:
        return {
            "generated_at": now,
            "role": normalized_role,
            "days": safe_days,
            "kpis": {
                "staff_total": 0,
                "with_activity_total": 0,
                "actions_total": 0,
                "ttn_actions_total": 0,
                "loyalty_issued_total": 0,
                "price_changes_total": 0,
            },
            "chart_by_day": _build_empty_chart_by_day(days=safe_days),
            "staff": [],
        }

    ttn_rows = {
        row["created_by_id"]: row
        for row in OrderNovaPoshtaWaybillEvent.objects.filter(created_by_id__in=staff_ids)
        .values("created_by_id")
        .annotate(
            ttn_actions=Count("id"),
            ttn_orders=Count("order_id", distinct=True),
            last_ttn_activity_at=Max("created_at"),
        )
    }

    loyalty_rows = {
        row["issued_by_id"]: row
        for row in LoyaltyPromoCode.objects.filter(issued_by_id__in=staff_ids)
        .values("issued_by_id")
        .annotate(
            loyalty_issued=Count("id"),
            loyalty_used=Count("id", filter=Q(usage_count__gt=0)),
            last_loyalty_activity_at=Max("created_at"),
        )
    }

    loyalty_discount_rows = {
        row["promo_code__issued_by_id"]: row
        for row in LoyaltyPromoRedemption.objects.filter(promo_code__issued_by_id__in=staff_ids)
        .values("promo_code__issued_by_id")
        .annotate(loyalty_discount_sum=Sum("total_discount"))
    }

    price_rows = {
        row["changed_by_id"]: row
        for row in PriceHistory.objects.filter(changed_by_id__in=staff_ids)
        .values("changed_by_id")
        .annotate(
            price_changes=Count("id"),
            price_manual=Count("id", filter=Q(source=PriceHistory.SOURCE_MANUAL)),
            price_import=Count("id", filter=Q(source=PriceHistory.SOURCE_IMPORT)),
            price_auto=Count("id", filter=Q(source=PriceHistory.SOURCE_AUTO)),
            last_price_activity_at=Max("created_at"),
        )
    }

    users_payload: list[dict] = []
    actions_total = 0
    ttn_total = 0
    loyalty_total = 0
    price_total = 0
    with_activity_total = 0

    for row in staff_rows:
        staff_id = row["id"]
        ttn = ttn_rows.get(staff_id, {})
        loyalty = loyalty_rows.get(staff_id, {})
        loyalty_discount = loyalty_discount_rows.get(staff_id, {})
        price = price_rows.get(staff_id, {})

        ttn_actions = int(ttn.get("ttn_actions") or 0)
        loyalty_issued = int(loyalty.get("loyalty_issued") or 0)
        price_changes = int(price.get("price_changes") or 0)
        activity_total = ttn_actions + loyalty_issued + price_changes

        actions_total += activity_total
        ttn_total += ttn_actions
        loyalty_total += loyalty_issued
        price_total += price_changes
        if activity_total > 0:
            with_activity_total += 1

        first_name = str(row.get("first_name") or "").strip()
        last_name = str(row.get("last_name") or "").strip()
        full_name = " ".join([first_name, last_name]).strip()

        last_candidates = [
            ttn.get("last_ttn_activity_at"),
            loyalty.get("last_loyalty_activity_at"),
            price.get("last_price_activity_at"),
        ]
        last_activity_at = None
        for value in last_candidates:
            if value is None:
                continue
            if last_activity_at is None or value > last_activity_at:
                last_activity_at = value

        users_payload.append(
            {
                "staff_id": str(staff_id),
                "staff_email": str(row.get("email") or ""),
                "staff_name": full_name,
                "actions_total": activity_total,
                "ttn_actions": ttn_actions,
                "ttn_orders": int(ttn.get("ttn_orders") or 0),
                "loyalty_issued": loyalty_issued,
                "loyalty_used": int(loyalty.get("loyalty_used") or 0),
                "loyalty_discount_sum": str(quantize_money(Decimal(loyalty_discount.get("loyalty_discount_sum") or 0))),
                "price_changes": price_changes,
                "price_manual": int(price.get("price_manual") or 0),
                "price_import": int(price.get("price_import") or 0),
                "price_auto": int(price.get("price_auto") or 0),
                "last_activity_at": last_activity_at,
            }
        )

    users_payload.sort(
        key=lambda item: (
            -int(item["actions_total"]),
            str(item["staff_name"] or "").lower(),
            str(item["staff_email"] or "").lower(),
        )
    )

    return {
        "generated_at": now,
        "role": normalized_role,
        "days": safe_days,
        "kpis": {
            "staff_total": len(staff_ids),
            "with_activity_total": with_activity_total,
            "actions_total": actions_total,
            "ttn_actions_total": ttn_total,
            "loyalty_issued_total": loyalty_total,
            "price_changes_total": price_total,
        },
        "chart_by_day": _build_chart_by_day(day_from=day_from, days=safe_days, staff_ids=staff_ids),
        "staff": users_payload,
    }


def _build_chart_by_day(*, day_from, days: int, staff_ids: list[int]) -> list[dict]:
    ttn_by_day = {
        str(row["created_at__date"]): int(row["total"])
        for row in OrderNovaPoshtaWaybillEvent.objects.filter(
            created_by_id__in=staff_ids,
            created_at__date__gte=day_from,
        )
        .values("created_at__date")
        .annotate(total=Count("id"))
    }
    loyalty_by_day = {
        str(row["created_at__date"]): int(row["total"])
        for row in LoyaltyPromoCode.objects.filter(
            issued_by_id__in=staff_ids,
            created_at__date__gte=day_from,
        )
        .values("created_at__date")
        .annotate(total=Count("id"))
    }
    price_by_day = {
        str(row["created_at__date"]): int(row["total"])
        for row in PriceHistory.objects.filter(
            changed_by_id__in=staff_ids,
            created_at__date__gte=day_from,
        )
        .values("created_at__date")
        .annotate(total=Count("id"))
    }

    rows: list[dict] = []
    for offset in range(days):
        day = day_from + timedelta(days=offset)
        key = str(day)
        ttn_actions = ttn_by_day.get(key, 0)
        loyalty_issued = loyalty_by_day.get(key, 0)
        price_changes = price_by_day.get(key, 0)
        rows.append(
            {
                "date": key,
                "ttn_actions": ttn_actions,
                "loyalty_issued": loyalty_issued,
                "price_changes": price_changes,
                "total": ttn_actions + loyalty_issued + price_changes,
            }
        )
    return rows


def _build_empty_chart_by_day(*, days: int) -> list[dict]:
    day_from = timezone.localdate() - timedelta(days=days - 1)
    rows: list[dict] = []
    for offset in range(days):
        day = day_from + timedelta(days=offset)
        rows.append(
            {
                "date": str(day),
                "ttn_actions": 0,
                "loyalty_issued": 0,
                "price_changes": 0,
                "total": 0,
            }
        )
    return rows
