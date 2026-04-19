from __future__ import annotations

import re
from typing import TypedDict

from django.utils.translation import gettext_lazy as _

from apps.commerce.models import Order, OrderItem
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierIntegrationError
from apps.supplier_imports.services.integrations.gpl_client import GplClient


class SupplierPayloadItem(TypedDict):
    item_id: str
    product_name: str
    product_sku: str
    quantity: int
    unit_price: str
    line_total: str
    gpl_product_id: int | None
    is_sendable: bool


class OrderSupplierService:
    _NOTE_ORDER_ID_PATTERN = re.compile(r"\[GPL_ORDER_ID:(?P<order_id>\d+)\]")

    def __init__(self) -> None:
        self.gpl_client = GplClient()

    def get_gpl_payload_preview(self, *, order: Order) -> dict:
        items = list(
            order.items.select_related(
                "selected_supplier_offer",
                "selected_supplier_offer__supplier",
                "recommended_supplier_offer",
                "recommended_supplier_offer__supplier",
            )
        )

        preview_items: list[SupplierPayloadItem] = []
        products_payload: list[dict[str, int]] = []

        for item in items:
            gpl_product_id = self._resolve_gpl_product_id(item)
            is_sendable = gpl_product_id is not None and int(item.quantity) > 0

            preview_items.append(
                {
                    "item_id": str(item.id),
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "quantity": int(item.quantity),
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.line_total),
                    "gpl_product_id": gpl_product_id,
                    "is_sendable": is_sendable,
                }
            )

            if is_sendable and gpl_product_id is not None:
                products_payload.append({"id": gpl_product_id, "count": int(item.quantity)})

        can_submit = len(products_payload) > 0 and all(item["is_sendable"] for item in preview_items)
        last_supplier_order_id = self.extract_last_gpl_order_id(order.operator_notes)

        return {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "products": products_payload,
            "items": preview_items,
            "can_submit": can_submit,
            "missing_count": sum(1 for item in preview_items if not item["is_sendable"]),
            "last_supplier_order_id": last_supplier_order_id,
        }

    def list_gpl_orders(self, *, page: int = 1) -> dict:
        token = self._get_gpl_access_token()
        return self.gpl_client.fetch_orders_page(access_token=token, page=page)

    def show_gpl_order(self, *, supplier_order_id: int) -> dict:
        token = self._get_gpl_access_token()
        return self.gpl_client.fetch_order(access_token=token, order_id=supplier_order_id)

    def create_gpl_order_for_local_order(
        self,
        *,
        order: Order,
        products: list[dict[str, int]] | None = None,
        test_mode: bool = False,
    ) -> dict:
        token = self._get_gpl_access_token()
        preview = self.get_gpl_payload_preview(order=order)

        payload_products = products or preview["products"]
        normalized_products: list[dict[str, int]] = []
        for row in payload_products:
            product_id = self._parse_positive_int(row.get("id"))
            count = self._parse_positive_int(row.get("count"))
            if product_id and count:
                normalized_products.append({"id": product_id, "count": count})

        if not normalized_products:
            raise SupplierIntegrationError(_("Невозможно оформить заказ поставщику: не удалось собрать корректный состав товаров."))

        payload = self.gpl_client.create_order(
            access_token=token,
            products=normalized_products,
            test_mode=test_mode,
        )

        supplier_order_id = self._extract_supplier_order_id(payload)
        if supplier_order_id is not None:
            self._append_order_note(order, f"[GPL_ORDER_ID:{supplier_order_id}]")

        return {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "supplier_order_id": supplier_order_id,
            "products": normalized_products,
            "response": payload,
        }

    def cancel_gpl_order_for_local_order(self, *, order: Order, supplier_order_id: int) -> dict:
        token = self._get_gpl_access_token()
        payload = self.gpl_client.cancel_order(access_token=token, order_id=supplier_order_id)
        self._append_order_note(order, f"[GPL_ORDER_CANCELLED:{supplier_order_id}]")
        return {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "supplier_order_id": int(supplier_order_id),
            "response": payload,
        }

    def extract_last_gpl_order_id(self, operator_notes: str) -> int | None:
        if not operator_notes:
            return None
        matches = list(self._NOTE_ORDER_ID_PATTERN.finditer(operator_notes))
        if not matches:
            return None
        return int(matches[-1].group("order_id"))

    def _get_gpl_access_token(self) -> str:
        integration = get_supplier_integration_by_code(source_code="gpl")
        if not integration.is_enabled:
            raise SupplierIntegrationError(_("Интеграция GPL отключена. Включите поставщика GPL в разделе Поставщики."))
        if not integration.access_token:
            raise SupplierIntegrationError(_("Нет access token GPL. Сначала получите токен в разделе Поставщики."))
        return integration.access_token

    def _resolve_gpl_product_id(self, item: OrderItem) -> int | None:
        candidates = [item.selected_supplier_offer, item.recommended_supplier_offer]

        for offer in candidates:
            if offer is None:
                continue
            supplier_code = (offer.supplier.code or "").strip().lower() if offer.supplier else ""
            if supplier_code != "gpl":
                continue

            parsed_from_sku = self._parse_positive_int(offer.supplier_sku)
            if parsed_from_sku:
                return parsed_from_sku

            raw_offer = (
                SupplierRawOffer.objects
                .filter(supplier__code="gpl", matched_product_id=item.product_id, external_sku=offer.supplier_sku)
                .order_by("-created_at")
                .first()
            )
            parsed_from_payload = self._extract_raw_offer_product_id(raw_offer)
            if parsed_from_payload:
                return parsed_from_payload

        raw_offer_fallback = (
            SupplierRawOffer.objects
            .filter(supplier__code="gpl", matched_product_id=item.product_id)
            .order_by("-created_at")
            .first()
        )
        parsed_fallback = self._extract_raw_offer_product_id(raw_offer_fallback)
        if parsed_fallback:
            return parsed_fallback

        return self._parse_positive_int(item.product_sku)

    def _extract_raw_offer_product_id(self, raw_offer: SupplierRawOffer | None) -> int | None:
        if raw_offer is None or not isinstance(raw_offer.raw_payload, dict):
            return None

        for key in ("id", "cid", "product_id"):
            parsed = self._parse_positive_int(raw_offer.raw_payload.get(key))
            if parsed:
                return parsed

        return None

    @staticmethod
    def _parse_positive_int(value: object) -> int | None:
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.isdigit():
                parsed = int(normalized)
                return parsed if parsed > 0 else None
        return None

    def _extract_supplier_order_id(self, payload: dict) -> int | None:
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        return self._parse_positive_int(data.get("id"))

    def _append_order_note(self, order: Order, note: str) -> None:
        next_note = self._merge_note(order.operator_notes, note)
        if next_note == order.operator_notes:
            return
        order.operator_notes = next_note
        order.save(update_fields=("operator_notes", "updated_at"))

    @staticmethod
    def _merge_note(existing: str, note: str) -> str:
        normalized = note.strip()
        if not normalized:
            return existing
        if not existing:
            return normalized
        return f"{existing}\n{normalized}"
