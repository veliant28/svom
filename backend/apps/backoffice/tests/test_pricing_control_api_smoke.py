from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import PricingPolicy, ProductPrice
from apps.users.models import User


class PricingControlAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="pricing-control@test.local",
            username="pricing-control-ops",
            password="demo12345",
            is_staff=True,
        )
        self.staff_token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.staff_token.key}"}

        self.brand = Brand.objects.create(name="Demo Brand", slug="demo-brand", is_active=True)
        self.root_category = Category.objects.create(name="Root", slug="root", is_active=True)
        self.child_category = Category.objects.create(name="Child", slug="child", parent=self.root_category, is_active=True)
        self.product = Product.objects.create(
            sku="SKU-1",
            article="ART-1",
            name="Demo Product",
            slug="demo-product",
            brand=self.brand,
            category=self.child_category,
            is_active=True,
            is_featured=True,
        )
        ProductPrice.objects.create(
            product=self.product,
            currency="UAH",
            purchase_price=Decimal("100.00"),
            landed_cost=Decimal("110.00"),
            final_price=Decimal("145.00"),
            raw_sale_price=Decimal("145.00"),
        )
        self.global_policy = PricingPolicy.objects.create(
            name="Global Demo Policy",
            scope=PricingPolicy.SCOPE_GLOBAL,
            priority=100,
            percent_markup=Decimal("20.00"),
            is_active=True,
        )

    def test_staff_can_get_pricing_control_panel(self):
        response = self.client.get(reverse("backoffice_api:pricing-control-panel"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["products_total"], 1)
        self.assertEqual(response.data["global_policy"]["percent_markup"], "20.00")
        self.assertIn("markup_buckets", response.data["chart"])

    def test_staff_can_get_category_impact(self):
        response = self.client.get(
            reverse("backoffice_api:pricing-category-impact"),
            {"category_id": str(self.root_category.id), "include_children": True},
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["affected_products"], 1)
        self.assertEqual(len(response.data["target_category_ids"]), 2)

    @patch("apps.backoffice.services.pricing_control_service.recalculate_product_prices_task")
    def test_staff_can_apply_global_markup(self, recalculate_task):
        recalculate_task.delay.return_value = None
        response = self.client.post(
            reverse("backoffice_api:pricing-global-markup"),
            {"percent_markup": "33.50", "dispatch_async": True},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.global_policy.refresh_from_db()
        self.assertEqual(self.global_policy.percent_markup, Decimal("33.50"))
        recalculate_task.delay.assert_called_once()

    @patch("apps.backoffice.services.pricing_control_service.recalculate_category_prices_task")
    def test_staff_can_apply_category_markup(self, recalculate_task):
        recalculate_task.delay.return_value = None
        response = self.client.post(
            reverse("backoffice_api:pricing-category-markup"),
            {
                "category_id": str(self.child_category.id),
                "percent_markup": "27.00",
                "include_children": False,
                "dispatch_async": True,
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        policy = PricingPolicy.objects.get(scope=PricingPolicy.SCOPE_CATEGORY, category=self.child_category)
        self.assertEqual(policy.percent_markup, Decimal("27.00"))
        recalculate_task.delay.assert_called_once()

    @patch("apps.backoffice.services.pricing_control_service.recalculate_product_prices_task")
    def test_staff_can_trigger_recalculate_all(self, recalculate_task):
        recalculate_task.delay.return_value = None
        response = self.client.post(
            reverse("backoffice_api:pricing-recalculate"),
            {"dispatch_async": True},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recalculate_task.delay.assert_called_once()
