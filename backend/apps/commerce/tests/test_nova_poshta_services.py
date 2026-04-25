from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.commerce.models import NovaPoshtaSenderProfile
from apps.commerce.services.nova_poshta.error_mapper import map_error_from_payload
from apps.commerce.services.nova_poshta.errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError
from apps.commerce.services.nova_poshta.payment_rules import PaymentRuleResolution, resolve_payment_rule, validate_sender_capabilities
from apps.commerce.services.nova_poshta.waybill_payloads import build_waybill_request_payload, build_waybill_upsert_payload


class NovaPoshtaPaymentRulesTests(SimpleTestCase):
    def test_private_sender_allows_cash_payment(self):
        rule = resolve_payment_rule(
            sender_type="private_person",
            requested_afterpayment=Decimal("500.00"),
            order_total=Decimal("1200.00"),
        )

        self.assertEqual(rule.payer_type, "Recipient")
        self.assertEqual(rule.payment_method, "Cash")
        self.assertEqual(rule.afterpayment_amount, Decimal("1200.00"))

    def test_business_sender_uses_control_payment_when_supported(self):
        rule = resolve_payment_rule(
            sender_type="business",
            requested_afterpayment=None,
            order_total=Decimal("1200.00"),
            sender_options={"CanAfterpaymentOnGoodsCost": True},
        )
        self.assertEqual(rule.afterpayment_amount, Decimal("1200.00"))

    def test_business_sender_keeps_requested_delivery_payment_method(self):
        rule = resolve_payment_rule(
            sender_type="fop",
            requested_afterpayment=Decimal("1200.00"),
            order_total=Decimal("1200.00"),
            requested_payment_method="Cash",
        )

        self.assertEqual(rule.payer_type, "Recipient")
        self.assertEqual(rule.payment_method, "Cash")
        self.assertEqual(rule.afterpayment_amount, Decimal("1200.00"))

    def test_business_sender_skips_control_payment_when_not_supported(self):
        rule = resolve_payment_rule(
            sender_type="business",
            requested_afterpayment=Decimal("1200.00"),
            order_total=Decimal("1200.00"),
            sender_options={"CanAfterpaymentOnGoodsCost": False, "CanNonCashPayment": True},
        )
        self.assertIsNone(rule.afterpayment_amount)

    def test_validate_capabilities_allows_sender_without_control_payment(self):
        validate_sender_capabilities(
            sender_type="business",
            options={"CanAfterpaymentOnGoodsCost": False, "CanNonCashPayment": True},
        )

    def test_error_mapper_returns_business_error_for_control_payment_message(self):
        exc = map_error_from_payload(
            payload={
                "errors": ["Послуга Контроль оплати недоступна"],
                "errorCodes": ["100"],
            },
            default_message="NP error",
        )

        self.assertIsInstance(exc, NovaPoshtaBusinessRuleError)

    def test_error_mapper_returns_integration_error_for_unknown_message(self):
        exc = map_error_from_payload(
            payload={"errors": ["Unexpected failure"]},
            default_message="NP error",
        )

        self.assertIsInstance(exc, NovaPoshtaIntegrationError)


class NovaPoshtaWaybillPayloadTests(SimpleTestCase):
    def test_build_upsert_payload_normalizes_options_seat(self):
        sender = NovaPoshtaSenderProfile(name="Main", sender_type="private_person", api_token="token")

        payload = build_waybill_upsert_payload(
            sender_profile=sender,
            data={
                "options_seat": [
                    {
                        "description": "Box 1",
                        "cost": "120.50",
                        "weight": "2.5",
                        "pack_refs": [" pack-a "],
                        "volumetric_width": "10",
                        "special_cargo": True,
                    },
                    {
                        "description": "Box 2",
                        "cost": "30",
                        "weight": "0",
                        "pack_ref": "pack-b",
                    },
                ],
            },
        )

        self.assertEqual(payload.seats_amount, 2)
        self.assertEqual(payload.weight, Decimal("2.501"))
        self.assertEqual(payload.cost, Decimal("150.50"))
        self.assertEqual(payload.description, "Box 1")
        self.assertEqual(payload.pack_refs, ("pack-a", "pack-b"))
        self.assertTrue(payload.options_seat[0].special_cargo)

    def test_build_request_payload_uses_options_seat_pack_refs(self):
        sender = NovaPoshtaSenderProfile(
            name="Main",
            sender_type="private_person",
            api_token="token",
            city_ref="sender-city",
            counterparty_ref="sender-counterparty",
            address_ref="sender-address",
            contact_ref="sender-contact",
            phone="380501111111",
        )
        payload = build_waybill_upsert_payload(
            sender_profile=sender,
            data={
                "delivery_type": "warehouse",
                "recipient_city_ref": "recipient-city",
                "recipient_address_ref": "warehouse-ref",
                "recipient_name": "Doe John",
                "recipient_phone": "380502222222",
                "options_seat": [
                    {"description": "Box", "cost": "100", "weight": "2", "pack_ref": "pack-a"},
                    {"description": "Tube", "cost": "50", "weight": "1", "pack_ref": "pack-b"},
                ],
            },
        )

        request_payload = build_waybill_request_payload(
            order=SimpleNamespace(total=Decimal("200"), order_number="ORD-1"),
            payload=payload,
            payment_resolution=PaymentRuleResolution(
                payer_type="Recipient",
                payment_method="Cash",
                afterpayment_amount=Decimal("200"),
            ),
        )

        self.assertEqual(request_payload["ServiceType"], "WarehouseWarehouse")
        self.assertEqual(request_payload["SeatsAmount"], "2")
        self.assertEqual(request_payload["Weight"], "3")
        self.assertEqual(request_payload["Cost"], "2")
        self.assertEqual(request_payload["AfterpaymentOnGoodsCost"], "2")
        self.assertEqual(request_payload["RecipientAddress"], "warehouse-ref")
        self.assertEqual(
            request_payload["OptionsSeat"],
            [
                {"weight": "2", "cost": "100", "description": "Box", "packRef": "pack-a"},
                {"weight": "1", "cost": "50", "description": "Tube", "packRef": "pack-b"},
            ],
        )
