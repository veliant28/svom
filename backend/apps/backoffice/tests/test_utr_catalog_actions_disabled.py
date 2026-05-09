from __future__ import annotations

from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.users.models import User


class UtrCatalogActionsDisabledTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="utr-catalog-disabled@test.local",
            first_name="utr-catalog-disabled",
            password="demo12345",
            is_staff=True,
        )
        token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {token.key}"}

        supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
        )

    def test_utr_brands_import_endpoint_is_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("backoffice_api:supplier-utr-brands-import")
