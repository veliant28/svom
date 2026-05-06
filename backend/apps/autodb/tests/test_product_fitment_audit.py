from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.autodb.services.fitment_quality import can_use_autodb_fitments_for_public_filtering
from apps.autodb.services.product_fitment_audit import AutoDbProductFitmentAuditService
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


class AutoDbProductFitmentAuditServiceTests(TestCase):
    databases = {"default", "auto_db_pro"}

    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand-audit", is_active=True)
        self.category = Category.objects.create(name="Engine", slug="engine-audit", is_active=True)
        self.product_a = Product.objects.create(
            sku="AUDIT-1",
            slug="audit-1",
            name="Шарнирный комплект",
            name_uk="Шарнірний комплект",
            name_ru="Шарнирный комплект",
            name_en="Joint kit",
            article="820099",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=300,
            autodb_article_number="820099",
            autodb_article_key="300:820099",
            is_active=True,
        )
        self.product_b = Product.objects.create(
            sku="AUDIT-2",
            slug="audit-2",
            name="Свічка запалювання",
            name_uk="Свічка запалювання",
            name_ru="Свеча зажигания",
            name_en="Spark plug",
            article="PLUG-1",
            brand=self.brand,
            category=self.category,
            autodb_supplier_id=301,
            autodb_article_number="PLUG-1",
            autodb_article_key="301:PLUG-1",
            is_active=True,
        )

        ProductFitment.objects.create(
            product=self.product_a,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=4215,
            linkage_type="PassengerCar",
            autodb_article_key="300:820099",
            supplier_id=300,
            article_number="820099",
        )
        ProductFitment.objects.create(
            product=self.product_b,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=4217,
            linkage_type="PassengerCar",
            autodb_article_key="301:PLUG-1",
            supplier_id=301,
            article_number="PLUG-1",
        )
        ProductFitment.objects.create(
            product=self.product_b,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=5570,
            linkage_type="PassengerCar",
            autodb_article_key="301:PLUG-1",
            supplier_id=301,
            article_number="PLUG-1",
        )

    def test_audit_summarizes_distribution_and_vehicle_labels(self):
        service = AutoDbProductFitmentAuditService()
        article_rows = {
            "300:820099": {"NormalizedDescription": "Шарнирный комплект"},
            "301:PLUG-1": {"NormalizedDescription": "Свеча зажигания"},
        }
        prd_titles = {
            "300:820099": "Шарнирный комплект",
            "301:PLUG-1": "Свеча зажигания",
        }
        article_li_rows = {
            "300:820099": [{"linkageTypeId": "PassengerCar", "linkageId": 4215}],
            "301:PLUG-1": [
                {"linkageTypeId": "PassengerCar", "linkageId": 4217},
                {"linkageTypeId": "PassengerCar", "linkageId": 5570},
            ],
        }
        car_contexts = {
            4215: {
                "make": "HONDA",
                "model": "LEGEND",
                "full_description": "HONDA LEGEND 3.2 i 24V (KA7)",
                "construction_interval": "1991-1996",
            },
            4217: {
                "make": "HONDA",
                "model": "LEGEND",
                "full_description": "HONDA LEGEND 3.2 i 24V (KA8)",
                "construction_interval": "1991-1996",
            },
            5570: {
                "make": "HONDA",
                "model": "LEGEND",
                "full_description": "HONDA LEGEND 3.5 i 24V (KA9)",
                "construction_interval": "1996-2000",
            },
        }

        with (
            patch.object(
                service,
                "_find_article_row",
                side_effect=lambda supplier_id, article_number: article_rows.get(f"{supplier_id}:{article_number}"),
            ),
            patch.object(
                service,
                "_resolve_prd_title",
                side_effect=lambda supplier_id, article_number: prd_titles.get(f"{supplier_id}:{article_number}", ""),
            ),
            patch.object(
                service,
                "_find_article_li_rows",
                side_effect=lambda supplier_id, article_number: article_li_rows.get(f"{supplier_id}:{article_number}", []),
            ),
            patch.object(service, "_find_passanger_car_contexts", return_value=car_contexts),
        ):
            rows, summary = service.audit_queryset(service.build_queryset(limit=10))

        self.assertEqual(summary.audited_products, 2)
        self.assertEqual(summary.total_fitments, 3)
        self.assertEqual(summary.min_fitments, 1)
        self.assertEqual(summary.max_fitments, 2)
        self.assertEqual(summary.avg_fitments, 1.5)
        self.assertEqual(summary.median_fitments, 1.5)
        self.assertTrue(any("HONDA / LEGEND" in row.sample_vehicle_label for row in rows))

    def test_suspicious_mismatch_is_detected(self):
        service = AutoDbProductFitmentAuditService()
        with (
            patch.object(service, "_find_article_row", return_value={"NormalizedDescription": "Амортизатор"}),
            patch.object(service, "_resolve_prd_title", return_value="Амортизатор"),
            patch.object(service, "_find_article_li_rows", return_value=[{"linkageTypeId": "PassengerCar", "linkageId": 4217}]),
            patch.object(
                service,
                "_find_passanger_car_contexts",
                return_value={4217: {"make": "HONDA", "model": "LEGEND", "full_description": "HONDA LEGEND 3.2 i 24V (KA8)"}},
            ),
        ):
            rows, summary = service.audit_queryset(service.build_queryset(product_id=str(self.product_b.id)))

        self.assertEqual(summary.suspicious_products, 1)
        self.assertIn("suspicious_link", rows[0].suspicious_flags)

    def test_audit_persists_suspicious_quality_and_excludes_fitments_from_public_filtering(self):
        service = AutoDbProductFitmentAuditService()
        with (
            patch.object(service, "_find_article_row", return_value={"NormalizedDescription": "Амортизатор"}),
            patch.object(service, "_resolve_prd_title", return_value="Амортизатор"),
            patch.object(service, "_find_article_li_rows", return_value=[{"linkageTypeId": "PassengerCar", "linkageId": 4217}]),
            patch.object(
                service,
                "_find_passanger_car_contexts",
                return_value={4217: {"make": "HONDA", "model": "LEGEND", "full_description": "HONDA LEGEND 3.2 i 24V (KA8)"}},
            ),
        ):
            rows, summary = service.audit_queryset(
                service.build_queryset(product_id=str(self.product_b.id)),
                persist_quality=True,
            )

        self.assertEqual(summary.suspicious_products, 1)
        self.assertEqual(rows[0].persisted_quality_status, AutoDbProductLinkQuality.STATUS_SUSPICIOUS)
        self.assertTrue(rows[0].persisted_excluded_from_public_filtering)
        quality = AutoDbProductLinkQuality.objects.get(product=self.product_b, autodb_article_key="301:PLUG-1")
        self.assertEqual(quality.status, AutoDbProductLinkQuality.STATUS_SUSPICIOUS)
        fitments = ProductFitment.objects.filter(product=self.product_b, source=ProductFitment.SOURCE_AUTODB_PRO)
        self.assertEqual(fitments.filter(excluded_from_public_filtering=True).count(), 2)
        self.assertFalse(can_use_autodb_fitments_for_public_filtering(product=self.product_b))
