from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Prefetch
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.commerce.models import Order, OrderItem
from apps.commerce.services.cart_calculations import calculate_cart_totals, get_line_total, quantize_money
from apps.commerce.services.cart_service import get_or_create_user_cart
from apps.commerce.services.delivery_snapshot import build_delivery_snapshot_from_checkout
from apps.commerce.services.monobank.client import MonobankApiError
from apps.commerce.services.monobank.invoice_service import create_invoice_for_order, get_order_payment
from apps.commerce.services.sellable_state import build_cart_item_warning, get_cart_item_sellable_snapshot
from apps.commerce.services.order_number import generate_order_number
from apps.pricing.models import SupplierOffer
from apps.users.models import User


@dataclass(frozen=True)
class CheckoutPreview:
    items_count: int
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    warnings: list[dict]


def resolve_delivery_fee(delivery_method: str) -> Decimal:
    delivery_fee_map = {
        Order.DELIVERY_PICKUP: Decimal("0.00"),
        Order.DELIVERY_COURIER: Decimal("150.00"),
        Order.DELIVERY_NOVA_POSHTA: Decimal("100.00"),
    }
    return delivery_fee_map.get(delivery_method, Decimal("0.00"))


def build_checkout_preview(*, user: User, delivery_method: str | None = None) -> CheckoutPreview:
    cart = get_or_create_user_cart(user)
    supplier_offers_prefetch = Prefetch(
        "product__supplier_offers",
        queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id"),
    )
    items = list(
        cart.items.select_related(
            "product",
            "product__product_price",
        ).prefetch_related(supplier_offers_prefetch)
    )
    totals = calculate_cart_totals(items)
    method = delivery_method or Order.DELIVERY_PICKUP
    delivery_fee = quantize_money(resolve_delivery_fee(method))
    warnings: list[dict] = []
    for item in items:
        snapshot = get_cart_item_sellable_snapshot(item)
        warning = build_cart_item_warning(item, snapshot)
        if warning:
            warnings.append(
                {
                    "product_id": str(item.product_id),
                    "product_name": item.product.name,
                    "product_sku": item.product.sku,
                    "warning": warning,
                }
            )

    return CheckoutPreview(
        items_count=totals.items_count,
        subtotal=totals.subtotal,
        delivery_fee=delivery_fee,
        total=quantize_money(totals.subtotal + delivery_fee),
        warnings=warnings,
    )


@transaction.atomic
def submit_checkout(*, user: User, payload: dict, monobank_webhook_url: str = "", monobank_redirect_url: str = "") -> Order:
    cart = get_or_create_user_cart(user)
    # Lock cart rows first without joined nullable tables; fetch relations in a separate query.
    locked_item_ids = list(cart.items.select_for_update().values_list("id", flat=True))
    supplier_offers_prefetch = Prefetch(
        "product__supplier_offers",
        queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id"),
    )
    items = list(
        cart.items.filter(id__in=locked_item_ids).select_related(
            "product",
            "product__product_price",
        ).prefetch_related(supplier_offers_prefetch)
    )

    if not items:
        raise ValidationError({"cart": _("Cart is empty.")})

    delivery_method = payload["delivery_method"]
    payment_method = payload["payment_method"]
    delivery_address = payload.get("delivery_address", "")
    delivery_snapshot = build_delivery_snapshot_from_checkout(
        delivery_method=delivery_method,
        delivery_address=delivery_address,
        delivery_snapshot=payload.get("delivery_snapshot"),
    )

    if delivery_method in (Order.DELIVERY_COURIER, Order.DELIVERY_NOVA_POSHTA) and not delivery_address:
        raise ValidationError({"delivery_address": _("Delivery address is required for selected delivery method.")})

    validation_errors: list[dict[str, str]] = []
    item_snapshots: dict[str, Any] = {}
    for item in items:
        snapshot = get_cart_item_sellable_snapshot(item)
        item_snapshots[str(item.id)] = snapshot

        if not snapshot.is_sellable:
            validation_errors.append(
                {
                    "product_id": str(item.product_id),
                    "product_sku": item.product.sku,
                    "code": "unavailable",
                    "message": _("Product became unavailable for checkout."),
                }
            )
            continue

        if snapshot.max_order_quantity is not None and item.quantity > snapshot.max_order_quantity:
            validation_errors.append(
                {
                    "product_id": str(item.product_id),
                    "product_sku": item.product.sku,
                    "code": "quantity_exceeds_stock",
                    "message": _("Requested quantity exceeds available stock."),
                }
            )

        if snapshot.current_sell_price <= Decimal("0"):
            validation_errors.append(
                {
                    "product_id": str(item.product_id),
                    "product_sku": item.product.sku,
                    "code": "invalid_price",
                    "message": _("Current sell price is unavailable."),
                }
            )

        if item.last_known_unit_price and Decimal(item.last_known_unit_price) != snapshot.current_sell_price:
            validation_errors.append(
                {
                    "product_id": str(item.product_id),
                    "product_sku": item.product.sku,
                    "code": "price_stale",
                    "message": _("Price changed since the item was added to cart."),
                }
            )

        if item.last_known_availability_status and item.last_known_availability_status != snapshot.availability_status:
            validation_errors.append(
                {
                    "product_id": str(item.product_id),
                    "product_sku": item.product.sku,
                    "code": "availability_stale",
                    "message": _("Availability changed since the item was added to cart."),
                }
            )

    if validation_errors:
        raise ValidationError(
            {
                "cart": _("Checkout blocked due to changed sellable state. Refresh cart and confirm again."),
                "items": validation_errors,
            }
        )

    totals = calculate_cart_totals(items)
    delivery_fee = quantize_money(resolve_delivery_fee(delivery_method))
    total = quantize_money(totals.subtotal + delivery_fee)
    order_currency = item_snapshots[str(items[0].id)].currency if items else "UAH"

    order = Order.objects.create(
        user=user,
        order_number=generate_order_number(),
        status=Order.STATUS_NEW,
        contact_full_name=payload["contact_full_name"],
        contact_phone=payload["contact_phone"],
        contact_email=payload["contact_email"],
        delivery_method=delivery_method,
        delivery_address=delivery_address,
        delivery_snapshot=delivery_snapshot,
        payment_method=payment_method,
        subtotal=totals.subtotal,
        delivery_fee=delivery_fee,
        total=total,
        currency=order_currency,
        customer_comment=payload.get("customer_comment", ""),
    )

    order_items: list[OrderItem] = []
    for item in items:
        snapshot = item_snapshots[str(item.id)]
        selected_offer_id = snapshot.selected_offer_id
        unit_price = snapshot.current_sell_price
        line_total = get_line_total(item)
        order_items.append(
            OrderItem(
                order=order,
                product=item.product,
                product_name=item.product.name,
                product_sku=item.product.sku,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
                recommended_supplier_offer_id=selected_offer_id,
                snapshot_currency=snapshot.currency,
                snapshot_sell_price=snapshot.current_sell_price,
                snapshot_availability_status=snapshot.availability_status,
                snapshot_availability_label=snapshot.availability_label,
                snapshot_estimated_delivery_days=snapshot.estimated_delivery_days,
                snapshot_procurement_source=snapshot.procurement_source_summary,
                snapshot_selected_offer_id=selected_offer_id,
                snapshot_offer_explainability=snapshot.explainability,
            )
        )

    OrderItem.objects.bulk_create(order_items)

    payment = get_order_payment(order)
    payment.amount = order.total
    payment.currency = order.currency
    if payment_method == Order.PAYMENT_MONOBANK:
        payment.provider = payment.PROVIDER_MONOBANK
        payment.method = payment.METHOD_MONOBANK
        payment.save(update_fields=("provider", "method", "amount", "currency", "updated_at"))
        try:
            create_invoice_for_order(
                order=order,
                webhook_url=monobank_webhook_url,
                redirect_url=monobank_redirect_url,
            )
        except MonobankApiError as exc:
            raise ValidationError({"payment_method": str(exc)}) from exc
    else:
        payment.provider = payment.PROVIDER_COD
        payment.method = payment.METHOD_CASH_ON_DELIVERY
        payment.status = payment.STATUS_PENDING
        payment.monobank_invoice_id = ""
        payment.monobank_page_url = ""
        payment.failure_reason = ""
        payment.save(
            update_fields=(
                "provider",
                "method",
                "status",
                "amount",
                "currency",
                "monobank_invoice_id",
                "monobank_page_url",
                "failure_reason",
                "updated_at",
            )
        )

    cart.items.all().delete()

    return order
