from __future__ import annotations

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.autodb.services.link_smoke_expectations import evaluate_link_smoke
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product


class LinkSmokeExpectationsTests(TestCase):
    def test_inactive_trusted_link_accepts_public_404(self):
        evaluation = evaluate_link_smoke(
            is_active=False,
            public_detail_status=status.HTTP_404_NOT_FOUND,
            trusted_link_visible=True,
            attributes_unchanged=True,
            fitments_unchanged=True,
            images_unchanged=True,
            price_unchanged=True,
            stock_unchanged=True,
        )
        self.assertEqual(evaluation.expected_public_detail_status, status.HTTP_404_NOT_FOUND)
        self.assertTrue(evaluation.status_matches_expectation)
        self.assertTrue(evaluation.smoke_ok)

    def test_active_trusted_link_requires_public_200(self):
        evaluation = evaluate_link_smoke(
            is_active=True,
            public_detail_status=status.HTTP_200_OK,
            trusted_link_visible=True,
            attributes_unchanged=True,
            fitments_unchanged=True,
            images_unchanged=True,
            price_unchanged=True,
            stock_unchanged=True,
        )
        self.assertEqual(evaluation.expected_public_detail_status, status.HTTP_200_OK)
        self.assertTrue(evaluation.status_matches_expectation)
        self.assertTrue(evaluation.smoke_ok)


class LinkSmokePublicDetailHostTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        brand = Brand.objects.create(name="Smoke Brand", slug="smoke-brand", is_active=True)
        category = Category.objects.create(name="Smoke Category", slug="smoke-category", is_active=True)
        self.active = Product.objects.create(
            sku="SMOKE-ACTIVE-1",
            article="SMOKE-ACTIVE-1",
            name="Smoke Active Product",
            slug="smoke-active-product",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=110,
            autodb_article_number="SMOKE-ACTIVE-1",
            autodb_article_key="110:SMOKE-ACTIVE-1",
        )
        self.inactive = Product.objects.create(
            sku="SMOKE-INACTIVE-1",
            article="SMOKE-INACTIVE-1",
            name="Smoke Inactive Product",
            slug="smoke-inactive-product",
            brand=brand,
            category=category,
            is_active=False,
            autodb_supplier_id=110,
            autodb_article_number="SMOKE-INACTIVE-1",
            autodb_article_key="110:SMOKE-INACTIVE-1",
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.active,
            autodb_article_key="110:SMOKE-ACTIVE-1",
            autodb_supplier_id=110,
            autodb_article_number="SMOKE-ACTIVE-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="test",
            evidence={"source": "test"},
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.inactive,
            autodb_article_key="110:SMOKE-INACTIVE-1",
            autodb_supplier_id=110,
            autodb_article_number="SMOKE-INACTIVE-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="test",
            evidence={"source": "test"},
        )
        self.client = APIClient()

    def test_public_detail_with_allowed_host(self):
        active_resp = self.client.get(f"/api/catalog/products/{self.active.slug}/", HTTP_HOST="localhost")
        inactive_resp = self.client.get(f"/api/catalog/products/{self.inactive.slug}/", HTTP_HOST="localhost")

        self.assertEqual(active_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(inactive_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_link_validity_checked_separately_from_public_visibility(self):
        active_trusted = AutoDbProductLinkQuality.objects.filter(
            product=self.active,
            autodb_article_key=self.active.autodb_article_key,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()
        inactive_trusted = AutoDbProductLinkQuality.objects.filter(
            product=self.inactive,
            autodb_article_key=self.inactive.autodb_article_key,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()

        self.assertTrue(active_trusted)
        self.assertTrue(inactive_trusted)
