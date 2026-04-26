from __future__ import annotations

from types import SimpleNamespace
from django.test import SimpleTestCase

from apps.commerce.models import VchasnoKasaSettings
from apps.commerce.services.vchasno_kasa.exceptions import VchasnoKasaConfigError
from apps.commerce.services.vchasno_kasa.payloads import (
    build_vchasno_sync_payload,
    build_vchasno_order_payload,
    get_selected_payment_methods,
    get_selected_tax_groups,
    normalize_payment_method_codes,
    normalize_tax_group_codes,
    reorder_payment_method_codes_for_order,
)


class VchasnoKasaPayloadsTests(SimpleTestCase):
    def test_normalize_payment_method_codes_keeps_known_codes_and_order(self):
        self.assertEqual(
            normalize_payment_method_codes([1, "17", " 20 ", "1", "invalid", 0]),
            ["1", "17", "20", "0"],
        )

    def test_normalize_tax_group_codes_keeps_known_codes_and_order(self):
        self.assertEqual(
            normalize_tax_group_codes(["а", "Б", "ик", "ГД", "x", "Б"]),
            ["А", "Б", "ИК", "ГД"],
        )

    def test_get_selected_payment_methods_returns_only_selected(self):
        settings = VchasnoKasaSettings(
            selected_payment_methods=["17", "2"],
            default_payment_type=1,
        )
        self.assertEqual(get_selected_payment_methods(settings=settings), ["17", "2"])

        settings.selected_payment_methods = []
        self.assertEqual(get_selected_payment_methods(settings=settings), [])

    def test_get_selected_tax_groups_returns_only_selected(self):
        settings = VchasnoKasaSettings(
            selected_tax_groups=["Б", "А"],
            default_tax_group="Е",
        )
        self.assertEqual(get_selected_tax_groups(settings=settings), ["Б", "А"])

        settings.selected_tax_groups = []
        self.assertEqual(get_selected_tax_groups(settings=settings), [])

    def test_build_payload_sends_selected_payments_and_uses_first_tax_group(self):
        settings = VchasnoKasaSettings(
            rro_fn="4001402705",
            selected_payment_methods=["17", "2", "1"],
            selected_tax_groups=["Б", "А"],
            send_customer_email=True,
        )
        item = SimpleNamespace(
            id=1,
            product_name="Oil filter",
            product_sku="OF-01",
            quantity=1,
            unit_price="120.00",
            line_total="120.00",
        )
        order = SimpleNamespace(
            order_number="ORD-001",
            total="120.00",
            payment_method="liqpay",
            contact_email="demo@example.com",
            contact_phone="+380000000001",
            items=SimpleNamespace(all=lambda: [item]),
        )
        receipt = SimpleNamespace(external_order_id="ext-1")

        payload = build_vchasno_order_payload(order=order, receipt=receipt, settings=settings)

        pays = payload["data"]["fiscal"]["receipt"]["pays"]
        row = payload["data"]["fiscal"]["receipt"]["rows"][0]
        self.assertEqual([item["type"] for item in pays], [17, 2, 1])
        self.assertEqual([item["sum"] for item in pays], [12000, 0, 0])
        self.assertEqual(row["taxgrp"], "Б")

    def test_reorder_payment_codes_uses_cod_mapping_when_available(self):
        ordered = reorder_payment_method_codes_for_order(
            selected_payment_methods=["1", "4", "17"],
            payment_method="cash_on_delivery",
        )
        self.assertEqual(ordered, ["4", "1", "17"])

    def test_reorder_payment_codes_uses_liqpay_mapping_when_available(self):
        ordered = reorder_payment_method_codes_for_order(
            selected_payment_methods=["2", "1", "17"],
            payment_method="liqpay",
        )
        self.assertEqual(ordered, ["17", "2", "1"])

    def test_reorder_payment_codes_falls_back_to_first_selected_if_no_match(self):
        ordered = reorder_payment_method_codes_for_order(
            selected_payment_methods=["1", "14", "15"],
            payment_method="monobank",
        )
        self.assertEqual(ordered, ["1", "14", "15"])

    def test_build_payload_raises_if_selected_codes_are_missing(self):
        settings = VchasnoKasaSettings(
            rro_fn="4001402705",
            selected_payment_methods=[],
            selected_tax_groups=[],
        )
        item = SimpleNamespace(
            id=1,
            product_name="Oil filter",
            product_sku="OF-01",
            quantity=1,
            unit_price="120.00",
            line_total="120.00",
        )
        order = SimpleNamespace(
            order_number="ORD-001",
            total="120.00",
            payment_method="liqpay",
            contact_email="",
            contact_phone="",
            items=SimpleNamespace(all=lambda: [item]),
        )
        receipt = SimpleNamespace(external_order_id="ext-1")

        with self.assertRaises(VchasnoKasaConfigError) as payment_error:
            build_vchasno_order_payload(order=order, receipt=receipt, settings=settings)
        self.assertEqual(payment_error.exception.code, "VCHASNO_KASA_PAYMENT_METHODS_REQUIRED")

        settings.selected_payment_methods = ["1"]
        with self.assertRaises(VchasnoKasaConfigError) as tax_error:
            build_vchasno_order_payload(order=order, receipt=receipt, settings=settings)
        self.assertEqual(tax_error.exception.code, "VCHASNO_KASA_TAX_GROUPS_REQUIRED")

    def test_sync_payload_does_not_send_unknown_filter_fields(self):
        receipt = SimpleNamespace(
            vchasno_order_number="ORD-001",
            external_order_id="ext-1",
        )

        payload = build_vchasno_sync_payload(receipt=receipt)

        self.assertEqual(payload, {})
