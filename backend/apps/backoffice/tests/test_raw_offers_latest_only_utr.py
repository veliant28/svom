from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.users.models import User
from apps.users.rbac import set_user_system_role


class RawOffersLatestOnlyUtrTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="ops-raw-offers@test.local",
            first_name="ops",
            password="demo12345",
            is_staff=True,
            is_superuser=False,
        )
        set_user_system_role(user=self.staff_user, role_code="administrator")
        self.staff_token = Token.objects.create(user=self.staff_user)

        self.utr_supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.utr_source = ImportSource.objects.create(
            code="utr",
            name="UTR Test",
            supplier=self.utr_supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
            auto_reprice=False,
        )

        older_run = ImportRun.objects.create(
            source=self.utr_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
        )
        SupplierRawOffer.objects.create(
            run=older_run,
            source=self.utr_source,
            supplier=self.utr_supplier,
            external_sku="UTR-OLD-1",
            article="OLD-1",
            normalized_article="OLD1",
            brand_name="UTR",
            normalized_brand="UTR",
            product_name="Older priced row",
            currency="UAH",
            price="100.00",
            stock_qty=1,
            lead_time_days=0,
            raw_payload={"Ціна": "100.00"},
            is_valid=True,
        )

        newer_run = ImportRun.objects.create(
            source=self.utr_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
            dry_run=False,
        )
        SupplierRawOffer.objects.create(
            run=newer_run,
            source=self.utr_source,
            supplier=self.utr_supplier,
            external_sku="UTR-NEW-1",
            article="NEW-1",
            normalized_article="NEW1",
            brand_name="UTR",
            normalized_brand="UTR",
            product_name="Newer no-price row",
            currency="UAH",
            price=None,
            stock_qty=2,
            lead_time_days=0,
            raw_payload={"Київська обл.": "2"},
            is_valid=True,
        )

        # Keep deterministic ordering for created_at.
        ImportRun.objects.filter(id=older_run.id).update(created_at=timezone.now() - timedelta(minutes=5))
        ImportRun.objects.filter(id=newer_run.id).update(created_at=timezone.now())
        self.older_run_id = str(older_run.id)
        self.newer_run_id = str(newer_run.id)

    def _auth(self) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {self.staff_token.key}"}

    def test_latest_only_for_utr_picks_latest_run_with_price(self):
        response = self.client.get(
            reverse("backoffice_api:raw-offer-list"),
            {"supplier": "utr", "latest_only": "true"},
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["count"], 0)
        self.assertEqual(str(response.data["results"][0]["run"]), self.older_run_id)
        self.assertEqual(response.data["results"][0]["price"], "100.00")
