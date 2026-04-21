from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.users.models import User
from apps.vehicles.models import VehicleEngine, VehicleGeneration, VehicleMake, VehicleModel, VehicleModification


class BackofficeProductFitmentsAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="fitments-ops@test.local",
            first_name="fitments-ops",
            password="demo12345",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="fitments-customer@test.local",
            first_name="fitments-customer",
            password="demo12345",
            is_staff=False,
        )
        self.staff_token = Token.objects.create(user=self.staff_user)
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.brand = Brand.objects.create(name="Toyota", slug="toyota", is_active=True)
        self.category = Category.objects.create(name="Body", slug="body", is_active=True)
        self.product = Product.objects.create(
            sku="TYT-001",
            article="TYT-001",
            name="Toyota Rear Lamp",
            slug="toyota-rear-lamp",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        self.make = VehicleMake.objects.create(name="Toyota", slug="toyota-auto", is_active=True)
        self.model = VehicleModel.objects.create(make=self.make, name="Corolla", slug="corolla", is_active=True)
        self.generation = VehicleGeneration.objects.create(model=self.model, name="E210", year_start=2019, is_active=True)
        self.engine = VehicleEngine.objects.create(
            generation=self.generation,
            name="1.8 Hybrid",
            code="2ZR-FXE",
            fuel_type=VehicleEngine.FUEL_HYBRID,
            is_active=True,
        )
        self.modification = VehicleModification.objects.create(
            engine=self.engine,
            name="Sedan",
            body_type="sedan",
            transmission="cvt",
            drivetrain="fwd",
            year_start=2019,
            is_active=True,
        )

    def _auth(self, token: str) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_staff_can_list_create_update_and_delete_fitments(self):
        list_response = self.client.get(
            reverse("backoffice_api:product-fitment-list-create"),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 0)

        create_response = self.client.post(
            reverse("backoffice_api:product-fitment-list-create"),
            {
                "product": str(self.product.id),
                "modification": str(self.modification.id),
                "note": "Rear axle only",
                "is_exact": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        fitment_id = create_response.data["id"]

        update_response = self.client.patch(
            reverse("backoffice_api:product-fitment-update", kwargs={"id": fitment_id}),
            {
                "note": "All trims",
                "is_exact": False,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(update_response.data["is_exact"])

        filtered = self.client.get(
            reverse("backoffice_api:product-fitment-list-create"),
            {
                "make": str(self.make.id),
                "is_exact": "false",
            },
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["count"], 1)

        delete_response = self.client.delete(
            reverse("backoffice_api:product-fitment-update", kwargs={"id": fitment_id}),
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductFitment.objects.filter(id=fitment_id).exists())

    def test_duplicate_fitment_is_rejected(self):
        ProductFitment.objects.create(
            product=self.product,
            modification=self.modification,
            note="Initial",
            is_exact=True,
        )
        duplicate_response = self.client.post(
            reverse("backoffice_api:product-fitment-list-create"),
            {
                "product": str(self.product.id),
                "modification": str(self.modification.id),
                "note": "Duplicate",
                "is_exact": True,
            },
            format="json",
            **self._auth(self.staff_token.key),
        )
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            "modification" in duplicate_response.data or "non_field_errors" in duplicate_response.data,
        )

    def test_non_staff_user_is_forbidden(self):
        response = self.client.get(
            reverse("backoffice_api:product-fitment-list-create"),
            **self._auth(self.regular_token.key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
