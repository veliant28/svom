from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User


class MatchingAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="ops-match@test.local",
            username="ops-match",
            password="demo12345",
            is_staff=True,
        )
        self.token = Token.objects.create(user=self.staff_user)

        self.brand = Brand.objects.create(name="ARAL", slug="aral", is_active=True)
        self.category = Category.objects.create(name="Oils", slug="oils", is_active=True)
        self.product = Product.objects.create(
            sku="AR-20488",
            article="AR-20488",
            name="Aral BlueTronic 10W-40 1Lx12",
            slug="aral-bluetronic-10w40-1l",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test")

        self.unmatched = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="SKU-NO",
            article="UNKNOWN",
            normalized_article="UNKNOWN",
            brand_name="NONE",
            normalized_brand="NONE",
            product_name="Unknown",
            currency="UAH",
            price=Decimal("100.00"),
            stock_qty=1,
            match_status=SupplierRawOffer.MATCH_STATUS_UNMATCHED,
            match_reason=SupplierRawOffer.MATCH_REASON_ARTICLE_CONFLICT,
            is_valid=False,
            skip_reason="article_conflict",
        )
        self.conflict = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="SKU-CONFLICT",
            article="AR-20488",
            normalized_article="AR20488",
            brand_name="ARAL",
            normalized_brand="ARAL",
            product_name="Aral",
            currency="UAH",
            price=Decimal("120.00"),
            stock_qty=5,
            match_status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED,
            match_reason=SupplierRawOffer.MATCH_REASON_AMBIGUOUS,
            match_candidate_product_ids=[str(self.product.id)],
            is_valid=False,
            skip_reason="ambiguous_match",
        )

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def test_matching_summary_and_lists(self):
        summary = self.client.get(reverse("backoffice_api:matching-summary"), **self._auth())
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data["unmatched"], 1)
        self.assertEqual(summary.data["conflicts"], 1)

        unmatched = self.client.get(reverse("backoffice_api:matching-unmatched-list"), **self._auth())
        self.assertEqual(unmatched.status_code, status.HTTP_200_OK)
        self.assertEqual(unmatched.data["count"], 1)

        conflicts = self.client.get(reverse("backoffice_api:matching-conflict-list"), **self._auth())
        self.assertEqual(conflicts.status_code, status.HTTP_200_OK)
        self.assertEqual(conflicts.data["count"], 1)

    def test_confirm_ignore_and_retry_actions(self):
        confirm = self.client.post(
            reverse("backoffice_api:matching-action-confirm"),
            {
                "raw_offer_id": str(self.conflict.id),
                "product_id": str(self.product.id),
            },
            format="json",
            **self._auth(),
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        self.conflict.refresh_from_db()
        self.assertEqual(self.conflict.match_status, SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED)

        ignore = self.client.post(
            reverse("backoffice_api:matching-action-ignore"),
            {
                "raw_offer_id": str(self.unmatched.id),
            },
            format="json",
            **self._auth(),
        )
        self.assertEqual(ignore.status_code, status.HTTP_200_OK)

        retry = self.client.post(
            reverse("backoffice_api:matching-action-retry"),
            {
                "raw_offer_id": str(self.unmatched.id),
            },
            format="json",
            **self._auth(),
        )
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
