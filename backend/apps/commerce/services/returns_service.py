from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.commerce.models import Order, OrderItem, ReturnRequest, ReturnRequestItem, ReturnRequestNumberSequence
from apps.core.models import ReturnServiceSettings
from apps.core.selectors import get_return_service_settings


RETURN_WINDOW_DAYS = 14
RETURN_TTN_DIGITS = 14
RETURN_TTN_EDIT_WINDOW = timedelta(hours=1)
DEFAULT_NON_RETURNABLE_CATEGORY_NAMES = (
    "Автохимия и масла",
    "Автохімія та оливи",
    "Auto chemistry and oils",
)

RECEIVED_TRACKING_STATUS_CODES = {"9", "10", "11"}
TRACKING_DATE_PATTERNS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d.%m.%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
)


@dataclass(frozen=True)
class ReturnableOrderItem:
    order_item: OrderItem
    max_return_quantity: int
    is_returnable: bool
    non_returnable_reason: str


def generate_return_number() -> str:
    with transaction.atomic():
        sequence, _ = ReturnRequestNumberSequence.objects.select_for_update().get_or_create(singleton_key=1)
        sequence.last_number = int(sequence.last_number or 0) + 1
        sequence.save(update_fields=("last_number",))
        return f"RET-{sequence.last_number:06d}"


def get_returns_settings() -> ReturnServiceSettings:
    settings = get_return_service_settings()
    if not settings.returns_non_returnable_category_ids:
        default_ids = _resolve_default_non_returnable_category_ids()
        if default_ids:
            settings.returns_non_returnable_category_ids = default_ids
            settings.returns_include_subcategories = True
            settings.save(update_fields=("returns_non_returnable_category_ids", "returns_include_subcategories", "updated_at"))
    return settings


def _resolve_default_non_returnable_category_ids() -> list[str]:
    queryset = Category.objects.filter(
        name__in=DEFAULT_NON_RETURNABLE_CATEGORY_NAMES,
    ) | Category.objects.filter(
        name_ru__in=DEFAULT_NON_RETURNABLE_CATEGORY_NAMES,
    ) | Category.objects.filter(
        name_uk__in=DEFAULT_NON_RETURNABLE_CATEGORY_NAMES,
    ) | Category.objects.filter(
        name_en__in=DEFAULT_NON_RETURNABLE_CATEGORY_NAMES,
    )
    return [str(category_id) for category_id in queryset.values_list("id", flat=True).distinct()]


def normalize_ua_phone(raw_value: str) -> str:
    digits = re.sub(r"\D+", "", str(raw_value or ""))
    if digits.startswith("380"):
        normalized_digits = digits
    elif digits.startswith("80"):
        normalized_digits = f"3{digits}"
    elif digits.startswith("0"):
        normalized_digits = f"38{digits}"
    else:
        normalized_digits = f"380{digits}"

    if len(normalized_digits) > 12:
        normalized_digits = normalized_digits[:12]

    if not re.fullmatch(r"380\d{9}", normalized_digits or ""):
        return ""
    return f"+{normalized_digits}"


def is_valid_ua_phone(raw_value: str) -> bool:
    return bool(normalize_ua_phone(raw_value))


def normalize_tracking_number(raw_value: str) -> str:
    digits = re.sub(r"\D+", "", str(raw_value or ""))
    if len(digits) != RETURN_TTN_DIGITS:
        return ""
    return digits


def format_tracking_number(raw_value: str) -> str:
    digits = normalize_tracking_number(raw_value)
    if not digits:
        return ""
    return f"{digits[:2]} {digits[2:6]} {digits[6:10]} {digits[10:14]}"


def is_tracking_edit_window_open(*, submitted_at, now=None) -> bool:
    if not submitted_at:
        return False
    now_ts = now or timezone.now()
    return now_ts <= (submitted_at + RETURN_TTN_EDIT_WINDOW)


def parse_tracking_received_at(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for pattern in TRACKING_DATE_PATTERNS:
        try:
            parsed = datetime.strptime(raw, pattern)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
        except ValueError:
            continue
    return None


def ensure_order_received_from_tracking(*, order: Order, status_code: str, status_payload: dict | None, synced_at=None) -> bool:
    normalized_status = str(status_code or "").strip()
    if normalized_status not in RECEIVED_TRACKING_STATUS_CODES:
        return False
    if order.received_at:
        return False

    payload = status_payload or {}
    date_candidates = (
        payload.get("DateReceived"),
        payload.get("DateFirstDayStorage"),
        payload.get("ScheduledDeliveryDate"),
    )
    received_at = None
    for candidate in date_candidates:
        parsed = parse_tracking_received_at(candidate)
        if parsed is not None:
            received_at = parsed
            break
    if received_at is None:
        received_at = synced_at or timezone.now()

    order.received_at = received_at
    order.received_at_source = Order.RECEIVED_SOURCE_NOVA_POSHTA_TRACKING
    order.return_eligible_until = received_at + timedelta(days=RETURN_WINDOW_DAYS)
    order.save(update_fields=("received_at", "received_at_source", "return_eligible_until", "updated_at"))
    return True


def ensure_order_received_from_completed_fallback(*, order: Order, completed_at=None) -> bool:
    if order.received_at:
        return False
    received_at = completed_at or timezone.now()
    order.received_at = received_at
    order.received_at_source = Order.RECEIVED_SOURCE_ORDER_COMPLETED_FALLBACK
    order.return_eligible_until = received_at + timedelta(days=RETURN_WINDOW_DAYS)
    order.save(update_fields=("received_at", "received_at_source", "return_eligible_until", "updated_at"))
    return True


def compute_return_day(*, received_at, created_at) -> int:
    if not received_at or not created_at:
        return 0
    delta_days = (created_at.date() - received_at.date()).days + 1
    return max(0, delta_days)


def build_return_day_label(*, received_at, created_at) -> str:
    day = compute_return_day(received_at=received_at, created_at=created_at)
    if day <= 0:
        return f"0/{RETURN_WINDOW_DAYS}"
    return f"{day}/{RETURN_WINDOW_DAYS}"


def is_order_return_window_open(order: Order, *, now=None) -> bool:
    now_ts = now or timezone.now()
    if order.status != Order.STATUS_COMPLETED:
        return False
    if not order.received_at or not order.return_eligible_until:
        return False
    return now_ts <= order.return_eligible_until


def _collect_descendant_category_ids(root_ids: set[str]) -> set[str]:
    if not root_ids:
        return set()
    child_map: dict[str, list[str]] = defaultdict(list)
    for category_id, parent_id in Category.objects.values_list("id", "parent_id"):
        if parent_id is None:
            continue
        child_map[str(parent_id)].append(str(category_id))

    resolved = set(root_ids)
    queue: deque[str] = deque(root_ids)
    while queue:
        parent_id = queue.popleft()
        for child_id in child_map.get(parent_id, []):
            if child_id in resolved:
                continue
            resolved.add(child_id)
            queue.append(child_id)
    return resolved


def resolve_non_returnable_category_ids(settings_obj: ReturnServiceSettings | None = None) -> set[str]:
    settings_obj = settings_obj or get_returns_settings()
    root_ids = {
        str(value).strip()
        for value in (settings_obj.returns_non_returnable_category_ids or [])
        if str(value).strip()
    }
    if not root_ids:
        return set()
    if not settings_obj.returns_include_subcategories:
        return root_ids
    return _collect_descendant_category_ids(root_ids)


def _product_category_id(product: Product) -> str:
    return str(product.category_id) if product.category_id else ""


def get_non_returnable_reason(*, product: Product, non_returnable_category_ids: set[str], locale: str | None = None) -> str:
    category_id = _product_category_id(product)
    if not category_id or category_id not in non_returnable_category_ids:
        return ""
    category = getattr(product, "category", None)
    if category is None and product.category_id:
        category = Category.objects.filter(id=product.category_id).first()
    if category is None:
        return "Категория не подлежит возврату."
    return f"Товар из категории «{category.get_localized_name(locale)}» не подлежит возврату."


def get_reserved_return_quantities_for_order(order: Order) -> dict[str, int]:
    blocked_statuses = (ReturnRequest.STATUS_REJECTED, ReturnRequest.STATUS_CANCELLED)
    rows = (
        ReturnRequestItem.objects.filter(order_item__order=order)
        .exclude(return_request__status__in=blocked_statuses)
        .values("order_item_id")
        .annotate(total=Sum("quantity_requested"))
    )
    result: dict[str, int] = {}
    for row in rows:
        key = str(row.get("order_item_id") or "")
        if not key:
            continue
        result[key] = int(row.get("total") or 0)
    return result


def build_returnable_order_items(*, order: Order, locale: str | None = None) -> list[ReturnableOrderItem]:
    settings_obj = get_returns_settings()
    non_returnable_categories = resolve_non_returnable_category_ids(settings_obj)
    reserved_quantities = get_reserved_return_quantities_for_order(order)

    items: list[ReturnableOrderItem] = []
    for order_item in order.items.select_related("product", "product__category").all():
        already_reserved = int(reserved_quantities.get(str(order_item.id), 0))
        max_return_quantity = max(0, int(order_item.quantity) - already_reserved)
        non_returnable_reason = get_non_returnable_reason(
            product=order_item.product,
            non_returnable_category_ids=non_returnable_categories,
            locale=locale,
        )
        is_returnable = bool(max_return_quantity > 0 and not non_returnable_reason)
        items.append(
            ReturnableOrderItem(
                order_item=order_item,
                max_return_quantity=max_return_quantity,
                is_returnable=is_returnable,
                non_returnable_reason=non_returnable_reason,
            )
        )
    return items


def validate_returns_settings_for_enable(settings_obj: ReturnServiceSettings) -> tuple[bool, str]:
    required_values = [
        settings_obj.returns_recipient_full_name,
        settings_obj.returns_recipient_phone,
        settings_obj.returns_region_label,
        settings_obj.returns_city_label,
        settings_obj.returns_np_warehouse_text,
    ]
    if any(not str(value or "").strip() for value in required_values):
        return False, "missing_required_data"
    if not is_valid_ua_phone(settings_obj.returns_recipient_phone):
        return False, "invalid_phone"
    return True, ""


def build_return_address_snapshot(settings_obj: ReturnServiceSettings | None = None) -> dict[str, str]:
    settings_obj = settings_obj or get_returns_settings()
    return {
        "recipient_full_name": str(settings_obj.returns_recipient_full_name or "").strip(),
        "recipient_phone": normalize_ua_phone(settings_obj.returns_recipient_phone),
        "region_ref": str(settings_obj.returns_region_ref or "").strip(),
        "region_label": str(settings_obj.returns_region_label or "").strip(),
        "city_ref": str(settings_obj.returns_city_ref or "").strip(),
        "city_label": str(settings_obj.returns_city_label or "").strip(),
        "np_warehouse_text": str(settings_obj.returns_np_warehouse_text or "").strip(),
    }


def sum_refund_amount(items: list[tuple[OrderItem, int]]) -> Decimal:
    total = Decimal("0.00")
    for order_item, quantity in items:
        total += (Decimal(order_item.unit_price or "0") * Decimal(max(0, quantity))).quantize(Decimal("0.01"))
    return total.quantize(Decimal("0.01"))
