from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.commerce.services.nova_poshta.error_mapper import map_error_from_payload
from apps.commerce.services.nova_poshta.errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError
from apps.commerce.services.nova_poshta.payment_rules import resolve_payment_rule, validate_sender_capabilities


class NovaPoshtaPaymentRulesTests(SimpleTestCase):
    def test_private_sender_allows_cash_payment(self):
        rule = resolve_payment_rule(
            sender_type="private_person",
            requested_afterpayment=Decimal("500.00"),
            order_total=Decimal("1200.00"),
        )

        self.assertEqual(rule.payer_type, "Recipient")
        self.assertEqual(rule.payment_method, "Cash")
        self.assertEqual(rule.afterpayment_amount, Decimal("500.00"))

    def test_business_sender_requires_afterpayment_amount(self):
        with self.assertRaises(NovaPoshtaBusinessRuleError):
            resolve_payment_rule(
                sender_type="business",
                requested_afterpayment=None,
                order_total=Decimal("1200.00"),
            )

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

    def test_validate_capabilities_fails_without_control_payment(self):
        with self.assertRaises(NovaPoshtaBusinessRuleError):
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
