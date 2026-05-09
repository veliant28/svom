from __future__ import annotations

from unittest.mock import patch

from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportSource, SupplierBrandAlias, SupplierPriceList
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.users.models import User


class SupplierWorkspaceAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="supplier-ops@test.local",
            first_name="supplier-ops",
            password="demo12345",
            is_staff=True,
        )
        self.staff_token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.staff_token.key}"}

        self.utr_supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.gpl_supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)

        self.utr_source = ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=self.utr_supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
        )
        self.gpl_source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.gpl_supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
        )

        brand = Brand.objects.create(name="UTR Brand", slug="utr-brand", is_active=True)
        category = Category.objects.create(name="UTR Category", slug="utr-category", is_active=True)
        product = Product.objects.create(
            sku="UTR-001",
            article="UTR-001",
            name="UTR Product",
            slug="utr-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        SupplierOffer.objects.create(
            supplier=self.utr_supplier,
            product=product,
            supplier_sku="U-001",
            purchase_price="123.45",
            stock_qty=5,
            is_available=True,
        )

    def test_supplier_workspace_main_endpoints(self):
        suppliers_response = self.client.get(reverse("backoffice_api:supplier-workspace-list"), **self.auth)
        self.assertEqual(suppliers_response.status_code, status.HTTP_200_OK)
        supplier_codes = {item["code"] for item in suppliers_response.data}
        self.assertIn("utr", supplier_codes)
        self.assertIn("gpl", supplier_codes)

        workspace_response = self.client.get(
            reverse("backoffice_api:supplier-workspace-detail", kwargs={"code": "utr"}),
            **self.auth,
        )
        self.assertEqual(workspace_response.status_code, status.HTTP_200_OK)
        self.assertEqual(workspace_response.data["supplier"]["code"], "utr")

        settings_response = self.client.patch(
            reverse("backoffice_api:supplier-workspace-settings", kwargs={"code": "utr"}),
            {
                "login": "utr-login",
                "password": "utr-password",
                "browser_fingerprint": "fp-1",
                "is_enabled": True,
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(settings_response.status_code, status.HTTP_200_OK)
        self.assertEqual(settings_response.data["connection"]["login"], "utr-login")

        prices_response = self.client.get(
            reverse("backoffice_api:supplier-prices-list", kwargs={"code": "utr"}),
            **self.auth,
        )
        self.assertEqual(prices_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(prices_response.data["count"], 1)

    def test_utr_brands_import_route_is_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("backoffice_api:supplier-utr-brands-import")

    @patch("apps.backoffice.services.supplier_workspace_service.UtrClient.check_connection")
    @patch("apps.backoffice.services.supplier_workspace_service.UtrClient.obtain_token")
    def test_utr_cooldown_blocks_second_import(self, obtain_token_mock, check_connection_mock):
        obtain_token_mock.return_value = type(
            "TokenPayload",
            (),
            {
                "access_token": "token-1",
                "refresh_token": "refresh-1",
                "access_expires_at": None,
                "refresh_expires_at": None,
            },
        )()
        check_connection_mock.return_value = {"ok": True}

        settings_response = self.client.patch(
            reverse("backoffice_api:supplier-workspace-settings", kwargs={"code": "utr"}),
            {"login": "utr-login", "password": "utr-password", "is_enabled": True},
            format="json",
            **self.auth,
        )
        self.assertEqual(settings_response.status_code, status.HTTP_200_OK)

        obtain_response = self.client.post(
            reverse("backoffice_api:supplier-token-obtain", kwargs={"code": "utr"}),
            {},
            format="json",
            **self.auth,
        )
        self.assertEqual(obtain_response.status_code, status.HTTP_200_OK)

        integration = get_supplier_integration_by_code(source_code="utr")
        integration.next_allowed_request_at = None
        integration.save(update_fields=("next_allowed_request_at", "updated_at"))

        first_import = self.client.post(
            reverse("backoffice_api:supplier-import-run", kwargs={"code": "utr"}),
            {"dry_run": False, "dispatch_async": False},
            format="json",
            **self.auth,
        )
        self.assertEqual(first_import.status_code, status.HTTP_200_OK)

        second_import = self.client.post(
            reverse("backoffice_api:supplier-import-run", kwargs={"code": "utr"}),
            {"dry_run": False, "dispatch_async": False},
            format="json",
            **self.auth,
        )
        self.assertEqual(second_import.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("retry_after_seconds", second_import.data)

    @patch("apps.backoffice.services.supplier_price_workflow_service.UtrClient.delete_pricelist")
    def test_utr_price_list_delete_not_ready_is_soft_and_deletes_local(self, delete_pricelist_mock):
        delete_pricelist_mock.side_effect = SupplierClientError(
            "Price list not found or not ready!",
            status_code=400,
        )

        integration = get_supplier_integration_by_code(source_code="utr")
        integration.access_token = "token-for-delete"
        integration.is_enabled = True
        integration.save(update_fields=("access_token", "is_enabled", "updated_at"))

        price_list = SupplierPriceList.objects.create(
            supplier=self.utr_supplier,
            source=self.utr_source,
            integration=integration,
            status=SupplierPriceList.STATUS_GENERATING,
            request_mode="utr_api",
            remote_id="remote-123",
        )

        response = self.client.post(
            reverse(
                "backoffice_api:supplier-price-list-delete",
                kwargs={"code": "utr", "price_list_id": str(price_list.id)},
            ),
            {},
            format="json",
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["deleted"])
        self.assertFalse(response.data["deleted_remote"])
        self.assertIn("not ready", response.data["remote_delete_error"].lower())
        self.assertFalse(SupplierPriceList.objects.filter(id=price_list.id).exists())
