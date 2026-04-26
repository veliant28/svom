import tempfile
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.autocatalog.models import CarMake, CarModel, CarModification, UtrArticleDetailMap, UtrDetailCarMap
from apps.catalog.models import Brand, Category, Product, ProductImage, UtrProductEnrichment
from apps.catalog.services.utr_product_enrichment import enrich_utr_product, request_visible_utr_enrichment
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand
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
            first_name="fitment-user",
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

        self.autocatalog_make = CarMake.objects.create(name="Toyota UTR", slug="toyota-utr")
        self.autocatalog_model = CarModel.objects.create(
            make=self.autocatalog_make,
            name="Camry UTR",
            slug="camry-utr",
        )
        self.autocatalog_modification = CarModification.objects.create(
            make=self.autocatalog_make,
            model=self.autocatalog_model,
            year=2020,
            modification="XV70",
            capacity="2.5",
            engine="A25A",
        )

        self.utr_supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.utr_source = ImportSource.objects.create(
            code="utr-fitment",
            name="UTR Fitment Source",
            supplier=self.utr_supplier,
            parser_type=ImportSource.PARSER_UTR,
        )
        self.utr_run = ImportRun.objects.create(
            source=self.utr_source,
            status=ImportRun.STATUS_SUCCESS,
            trigger="test",
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

    def test_product_detail_contains_utr_fitments_when_manual_fitments_missing(self):
        product = Product.objects.create(
            sku="UTR-DETAIL-CARD-001",
            article="UTR-DETAIL-CARD-001",
            name="UTR Detail Card Product",
            slug="utr-detail-card-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")

        detail_id = "5001"
        UtrArticleDetailMap.objects.create(
            article=product.article,
            normalized_article=normalize_article(product.article),
            brand_name=self.brand.name,
            normalized_brand=normalize_brand(self.brand.name),
            utr_detail_id=detail_id,
        )
        UtrDetailCarMap.objects.create(
            utr_detail_id=detail_id,
            car_modification=self.autocatalog_modification,
        )
        self._create_utr_raw_offer(
            product=product,
            article=product.article,
            brand_name=self.brand.name,
        )

        response = self.client.get(reverse("catalog_api:product-detail", kwargs={"slug": "utr-detail-card-product"}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["fitments"]), 1)
        fitments = response.data["fitments"]
        self.assertTrue(any(item["make"] == "Toyota UTR" and item["model"] == "Camry UTR" for item in fitments))

    def test_product_fitment_options_return_full_utr_make_and_model_facets(self):
        product = Product.objects.create(
            sku="UTR-FACETS-001",
            article="UTR-FACETS-001",
            name="UTR Facets Product",
            slug="utr-facets-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")

        detail_id = "5101"
        UtrArticleDetailMap.objects.create(
            article=product.article,
            normalized_article=normalize_article(product.article),
            brand_name=self.brand.name,
            normalized_brand=normalize_brand(self.brand.name),
            utr_detail_id=detail_id,
        )
        self._create_utr_raw_offer(
            product=product,
            article=product.article,
            brand_name=self.brand.name,
        )
        other_make = CarMake.objects.create(name="Lancia UTR", slug="lancia-utr")
        other_model = CarModel.objects.create(make=other_make, name="Dedra UTR", slug="dedra-utr")
        other_modification = CarModification.objects.create(
            make=other_make,
            model=other_model,
            year=1994,
            modification="SW",
            engine="1.8",
        )
        UtrDetailCarMap.objects.create(utr_detail_id=detail_id, car_modification=self.autocatalog_modification)
        UtrDetailCarMap.objects.create(utr_detail_id=detail_id, car_modification=other_modification)

        response = self.client.get(reverse("catalog_api:product-fitment-options", kwargs={"slug": product.slug}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({item["value"] for item in response.data["makes"]}, {"Toyota UTR", "Lancia UTR"})
        self.assertEqual({item["value"] for item in response.data["models"]}, {"Camry UTR", "Dedra UTR"})
        self.assertEqual(response.data["total_fitments"], 2)

        model_response = self.client.get(
            reverse("catalog_api:product-fitment-options", kwargs={"slug": product.slug}),
            {"make": "Lancia UTR"},
        )

        self.assertEqual(model_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["value"] for item in model_response.data["models"]], ["Dedra UTR"])

    def test_product_fitment_rows_are_loaded_by_selected_utr_make_and_model(self):
        product = Product.objects.create(
            sku="UTR-ROWS-001",
            article="UTR-ROWS-001",
            name="UTR Rows Product",
            slug="utr-rows-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")

        detail_id = "5201"
        UtrArticleDetailMap.objects.create(
            article=product.article,
            normalized_article=normalize_article(product.article),
            brand_name=self.brand.name,
            normalized_brand=normalize_brand(self.brand.name),
            utr_detail_id=detail_id,
        )
        self._create_utr_raw_offer(
            product=product,
            article=product.article,
            brand_name=self.brand.name,
        )
        other_make = CarMake.objects.create(name="Mazda UTR", slug="mazda-utr")
        other_model = CarModel.objects.create(make=other_make, name="626 UTR", slug="626-utr")
        other_modification = CarModification.objects.create(
            make=other_make,
            model=other_model,
            year=2001,
            modification="Sedan",
            engine="2.0",
        )
        second_toyota = CarModification.objects.create(
            make=self.autocatalog_make,
            model=self.autocatalog_model,
            year=2021,
            modification="XV70 facelift",
            engine="A25A",
        )
        UtrDetailCarMap.objects.create(utr_detail_id=detail_id, car_modification=self.autocatalog_modification)
        UtrDetailCarMap.objects.create(utr_detail_id=detail_id, car_modification=second_toyota)
        UtrDetailCarMap.objects.create(utr_detail_id=detail_id, car_modification=other_modification)

        response = self.client.get(
            reverse("catalog_api:product-fitment-rows", kwargs={"slug": product.slug}),
            {
                "make": "Toyota UTR",
                "model": "Camry UTR",
                "car_modification": str(second_toyota.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual([item["make"] for item in response.data["results"]], ["Toyota UTR", "Toyota UTR"])
        self.assertEqual(response.data["results"][0]["modification"], "XV70 facelift")

    @patch("apps.catalog.services.utr_product_enrichment._resolve_utr_access_token", return_value="test-token")
    @patch("apps.catalog.services.utr_product_enrichment.UtrClient")
    @patch("apps.catalog.services.utr_product_enrichment._enqueue_enrichment_task")
    def test_lazy_utr_enrichment_resolves_missing_detail_id_and_persists_fallback(
        self,
        _enqueue_mock,
        client_class,
        _token_mock,
    ):
        cache.clear()
        product = Product.objects.create(
            sku="LAZY-UTR-001-SKU",
            article="LAZY-UTR-001",
            name="Lazy UTR Product",
            slug="lazy-utr-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")
        self._create_utr_raw_offer(product=product, article=product.article, brand_name=self.brand.name)

        status_rows = request_visible_utr_enrichment(product_ids=[str(product.id)], enqueue=True)

        self.assertEqual(status_rows[0]["status"], UtrProductEnrichment.STATUS_QUEUED)
        self.assertTrue(status_rows[0]["queued"])

        client = client_class.return_value
        client.search_details.return_value = [
            {
                "id": "93001",
                "article": product.article,
                "displayBrand": self.brand.name,
            }
        ]
        client.fetch_detail.return_value = {
            "id": 93001,
            "images": [
                {
                    "fullImagePath": "https://cdn.example.test/lazy-utr-001.webp",
                }
            ],
        }
        client.fetch_characteristics.return_value = [
            {
                "attribute": {"title": "Voltage"},
                "value": "12V",
            }
        ]
        client.fetch_applicability.return_value = [
            {
                "manufacturer": "Lazy Toyota",
                "models": [
                    {
                        "model": "Lazy Camry",
                        "cars": [
                            {
                                "car": "Sedan",
                                "startDateAt": "2020-01-01",
                                "capacity": "2.5",
                                "engine": "A25A",
                            }
                        ],
                    }
                ],
            }
        ]

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch(
                    "apps.catalog.services.utr_product_enrichment._download_image",
                    return_value=(b"fake-image", "image/webp"),
                ):
                    result = enrich_utr_product(product_id=str(product.id))

                self.assertEqual(result["status"], UtrProductEnrichment.STATUS_FETCHED)
                self.assertEqual(result["utr_detail_id"], "93001")
                self.assertEqual(result["characteristics_count"], 1)
                self.assertTrue(result["created_image"])

                product.refresh_from_db()
                self.assertEqual(product.utr_detail_id, "93001")
                self.assertTrue(ProductImage.objects.filter(product=product).exists())

        self.assertTrue(
            UtrArticleDetailMap.objects.filter(
                normalized_article=normalize_article(product.article),
                normalized_brand=normalize_brand(self.brand.name),
                utr_detail_id="93001",
            ).exists()
        )
        enrichment = UtrProductEnrichment.objects.get(product=product)
        self.assertEqual(enrichment.characteristics_payload[0]["value"], "12V")
        self.assertEqual(enrichment.images_payload[0]["fullImagePath"], "https://cdn.example.test/lazy-utr-001.webp")
        self.assertTrue(UtrDetailCarMap.objects.filter(utr_detail_id="93001").exists())

    def test_products_filter_by_car_modification_supports_utr_detail_and_article_map(self):
        product_with_detail = Product.objects.create(
            sku="UTR-DETAIL-001",
            article="UTR-DETAIL-001",
            utr_detail_id="1001",
            name="UTR Detail Product",
            slug="utr-detail-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        product_with_article_map = Product.objects.create(
            sku="UTR-ARTICLE-001",
            article="CPR8EA-9",
            name="UTR Article Product",
            slug="utr-article-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        product_unmatched = Product.objects.create(
            sku="UTR-UNMATCHED-001",
            article="NO-MAP-001",
            name="UTR Unmatched Product",
            slug="utr-unmatched-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        for product in (product_with_detail, product_with_article_map, product_unmatched):
            ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")

        UtrDetailCarMap.objects.create(
            utr_detail_id="1001",
            car_modification=self.autocatalog_modification,
        )
        UtrArticleDetailMap.objects.create(
            article="CPR8EA-9",
            normalized_article=normalize_article("CPR8EA-9"),
            brand_name=self.brand.name,
            normalized_brand=normalize_brand(self.brand.name),
            utr_detail_id="1001",
        )

        self._create_utr_raw_offer(
            product=product_with_article_map,
            article="CPR8EA-9",
            brand_name=self.brand.name,
        )
        self._create_utr_raw_offer(
            product=product_unmatched,
            article="NO-MAP-001",
            brand_name=self.brand.name,
        )

        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "car_modification": str(self.autocatalog_modification.id),
                "fitment": "only",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertSetEqual(slugs, {"utr-detail-product", "utr-article-product"})

    def test_products_filter_by_autocatalog_garage_vehicle_uses_local_utr_mappings(self):
        product = Product.objects.create(
            sku="UTR-GARAGE-001",
            article="GARAGE-001",
            utr_detail_id="2001",
            name="UTR Garage Product",
            slug="utr-garage-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=product, final_price="100.00", currency="UAH")
        UtrDetailCarMap.objects.create(
            utr_detail_id="2001",
            car_modification=self.autocatalog_modification,
        )

        garage_vehicle = GarageVehicle.objects.create(
            user=self.user,
            car_modification=self.autocatalog_modification,
            vin="JTNB11HKTESTUTR999",
            year=2020,
        )

        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "garage_vehicle": str(garage_vehicle.id),
                "fitment": "only",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "utr-garage-product")
        self.assertTrue(response.data["results"][0]["has_fitment_data"])

    @override_settings(SEARCH_BACKEND="db")
    def test_products_search_and_car_filter_work_together(self):
        product_matching_vehicle = Product.objects.create(
            sku="UTR-SEARCH-OK-001",
            article="SEARCH-OK-001",
            utr_detail_id="3001",
            name="Brake Query Match",
            slug="brake-query-match",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        product_other_vehicle = Product.objects.create(
            sku="UTR-SEARCH-OTHER-001",
            article="SEARCH-OTHER-001",
            utr_detail_id="4001",
            name="Brake Query Other",
            slug="brake-query-other",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        ProductPrice.objects.create(product=product_matching_vehicle, final_price="100.00", currency="UAH")
        ProductPrice.objects.create(product=product_other_vehicle, final_price="100.00", currency="UAH")

        UtrDetailCarMap.objects.create(
            utr_detail_id="3001",
            car_modification=self.autocatalog_modification,
        )

        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "q": "Brake Query",
                "car_modification": str(self.autocatalog_modification.id),
                "fitment": "only",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "brake-query-match")

    def test_vehicle_fitment_is_bypassed_for_auto_chemistry_subcategory(self):
        auto_root = Category.objects.create(
            name="Автохімія та аксесуари",
            name_uk="Автохімія та аксесуари",
            name_ru="Автохимия и аксессуары",
            name_en="Auto chemicals and accessories",
            slug="автохіміятааксесуари",
            is_active=True,
        )
        auto_child = Category.objects.create(
            name="Очисники",
            slug="очисники",
            parent=auto_root,
            is_active=True,
        )
        product_matching_vehicle = Product.objects.create(
            sku="AUTO-CHEM-OK-001",
            article="AUTO-CHEM-OK-001",
            name="Auto Chemistry Compatible",
            slug="auto-chemistry-compatible",
            brand=self.brand,
            category=auto_child,
            is_active=True,
        )
        product_other_vehicle = Product.objects.create(
            sku="AUTO-CHEM-OTHER-001",
            article="AUTO-CHEM-OTHER-001",
            name="Auto Chemistry Other Vehicle",
            slug="auto-chemistry-other-vehicle",
            brand=self.brand,
            category=auto_child,
            is_active=True,
        )
        ProductPrice.objects.create(product=product_matching_vehicle, final_price="100.00", currency="UAH")
        ProductPrice.objects.create(product=product_other_vehicle, final_price="100.00", currency="UAH")
        ProductFitment.objects.create(product=product_matching_vehicle, modification=self.camry_mod, is_exact=True)
        ProductFitment.objects.create(product=product_other_vehicle, modification=self.bmw_mod, is_exact=True)

        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "garage_vehicle": str(self.garage_vehicle.id),
                "fitment": "only",
                "category_id": str(auto_child.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertSetEqual(slugs, {"auto-chemistry-compatible", "auto-chemistry-other-vehicle"})
        self.assertTrue(all(item["fitment_badge_hidden"] is True for item in response.data["results"]))

    def test_vehicle_fitment_is_bypassed_for_tires_subcategory_via_slug(self):
        tires_root = Category.objects.create(
            name="Шини та диски",
            name_uk="Шини та диски",
            name_ru="Шины и диски",
            name_en="Tires and wheels",
            slug="шинитадиски",
            is_active=True,
        )
        tires_child = Category.objects.create(
            name="Легкові шини",
            slug="легковішини",
            parent=tires_root,
            is_active=True,
        )
        product_matching_vehicle = Product.objects.create(
            sku="TIRES-OK-001",
            article="TIRES-OK-001",
            name="Tires Compatible",
            slug="tires-compatible",
            brand=self.brand,
            category=tires_child,
            is_active=True,
        )
        product_other_vehicle = Product.objects.create(
            sku="TIRES-OTHER-001",
            article="TIRES-OTHER-001",
            name="Tires Other Vehicle",
            slug="tires-other-vehicle",
            brand=self.brand,
            category=tires_child,
            is_active=True,
        )
        ProductPrice.objects.create(product=product_matching_vehicle, final_price="100.00", currency="UAH")
        ProductPrice.objects.create(product=product_other_vehicle, final_price="100.00", currency="UAH")
        ProductFitment.objects.create(product=product_matching_vehicle, modification=self.camry_mod, is_exact=True)
        ProductFitment.objects.create(product=product_other_vehicle, modification=self.bmw_mod, is_exact=True)

        response = self.client.get(
            reverse("catalog_api:product-list"),
            {
                "garage_vehicle": str(self.garage_vehicle.id),
                "fitment": "only",
                "category": tires_child.slug,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertSetEqual(slugs, {"tires-compatible", "tires-other-vehicle"})
        self.assertTrue(all(item["fitment_badge_hidden"] is True for item in response.data["results"]))

    def _create_utr_raw_offer(self, *, product: Product, article: str, brand_name: str) -> SupplierRawOffer:
        return SupplierRawOffer.objects.create(
            run=self.utr_run,
            source=self.utr_source,
            supplier=self.utr_supplier,
            external_sku=article,
            article=article,
            normalized_article=normalize_article(article),
            brand_name=brand_name,
            normalized_brand=normalize_brand(brand_name),
            product_name=product.name,
            currency="UAH",
            price="100.00",
            stock_qty=1,
            lead_time_days=1,
            matched_product=product,
        )
