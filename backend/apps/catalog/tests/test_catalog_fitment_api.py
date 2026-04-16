from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice
from apps.users.models import GarageVehicle, User
from apps.vehicles.models import VehicleEngine, VehicleGeneration, VehicleMake, VehicleModel, VehicleModification


class CatalogFitmentAPITests(APITestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand F", slug="brand-f", is_active=True)
        self.category = Category.objects.create(name="Category F", slug="category-f", is_active=True)

        self.product_camry = Product.objects.create(
            sku="FIT-CAMRY-001",
            article="FIT-CAMRY-001",
            name="Camry Fit Product",
            slug="camry-fit-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.product_bmw = Product.objects.create(
            sku="FIT-BMW-001",
            article="FIT-BMW-001",
            name="BMW Fit Product",
            slug="bmw-fit-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.product_unknown = Product.objects.create(
            sku="FIT-UNKNOWN-001",
            article="FIT-UNKNOWN-001",
            name="Unknown Fit Product",
            slug="unknown-fit-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        for product in (self.product_camry, self.product_bmw, self.product_unknown):
            ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")

        toyota = VehicleMake.objects.create(name="Toyota", slug="toyota-fit", is_active=True)
        bmw = VehicleMake.objects.create(name="BMW", slug="bmw-fit", is_active=True)

        camry = VehicleModel.objects.create(make=toyota, name="Camry", slug="camry-fit", is_active=True)
        series3 = VehicleModel.objects.create(make=bmw, name="3 Series", slug="3-series-fit", is_active=True)

        camry_gen = VehicleGeneration.objects.create(model=camry, name="XV70", year_start=2017, is_active=True)
        bmw_gen = VehicleGeneration.objects.create(model=series3, name="G20", year_start=2018, is_active=True)

        camry_engine = VehicleEngine.objects.create(
            generation=camry_gen,
            name="2.5 Hybrid",
            code="A25A",
            fuel_type=VehicleEngine.FUEL_HYBRID,
            is_active=True,
        )
        bmw_engine = VehicleEngine.objects.create(
            generation=bmw_gen,
            name="330i",
            code="B48",
            fuel_type=VehicleEngine.FUEL_PETROL,
            is_active=True,
        )

        self.camry_mod = VehicleModification.objects.create(
            engine=camry_engine,
            name="Sedan",
            year_start=2019,
            is_active=True,
        )
        self.bmw_mod = VehicleModification.objects.create(
            engine=bmw_engine,
            name="Sedan",
            year_start=2019,
            is_active=True,
        )

        ProductFitment.objects.create(product=self.product_camry, modification=self.camry_mod, is_exact=True)
        ProductFitment.objects.create(product=self.product_bmw, modification=self.bmw_mod, is_exact=True)

        self.user = User.objects.create_user(
            email="fitment@test.local",
            username="fitment-user",
            password="pass12345",
        )
        self.garage_vehicle = GarageVehicle.objects.create(
            user=self.user,
            make=toyota,
            model=camry,
            generation=camry_gen,
            engine=camry_engine,
            modification=self.camry_mod,
            vin="JTNB11HKTESTFIT001",
            year=2020,
        )

    def test_products_filter_by_modification_returns_only_compatible(self):
        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "modification": str(self.camry_mod.id),
                "fitment": "only",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["camry-fit-product"])

    def test_products_filter_by_garage_vehicle_returns_only_compatible(self):
        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "garage_vehicle": str(self.garage_vehicle.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["camry-fit-product"])

    def test_products_list_exposes_fitment_awareness_flags(self):
        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "garage_vehicle": str(self.garage_vehicle.id),
                "fitment": "all",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        results = {item["slug"]: item for item in response.data["results"]}

        self.assertTrue(results["camry-fit-product"]["fits_selected_vehicle"])
        self.assertTrue(results["camry-fit-product"]["has_fitment_data"])

        self.assertFalse(results["bmw-fit-product"]["fits_selected_vehicle"])
        self.assertTrue(results["bmw-fit-product"]["has_fitment_data"])

        self.assertFalse(results["unknown-fit-product"]["has_fitment_data"])

    def test_product_detail_contains_fitments(self):
        response = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "camry-fit-product"}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["fitments"]), 1)
        fitment = response.data["fitments"][0]
        self.assertEqual(fitment["make"], "Toyota")
        self.assertEqual(fitment["model"], "Camry")
        self.assertEqual(fitment["modification"], "Sedan")
