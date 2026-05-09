from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product
from apps.compatibility.models import ProductFitment


class PersistAutoDbFitmentQualityCommandTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="Brand", slug="persist-fit-brand", is_active=True)
        category = Category.objects.create(name="Category", slug="persist-fit-cat", is_active=True)
        self.clean = Product.objects.create(
            sku="PERSIST-CLEAN-1",
            article="PERSIST-CLEAN-1",
            name="Clean",
            slug="persist-clean",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="PERSIST-CLEAN-1",
            autodb_article_key="324:PERSIST-CLEAN-1",
        )
        self.suspicious = Product.objects.create(
            sku="PERSIST-SUSP-1",
            article="PERSIST-SUSP-1",
            name="Suspicious",
            slug="persist-suspicious",
            brand=brand,
            category=category,
            is_active=True,
            autodb_supplier_id=324,
            autodb_article_number="PERSIST-SUSP-1",
            autodb_article_key="324:PERSIST-SUSP-1",
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.clean,
            autodb_article_key="324:PERSIST-CLEAN-1",
            autodb_supplier_id=324,
            autodb_article_number="PERSIST-CLEAN-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        AutoDbProductLinkQuality.objects.create(
            product=self.suspicious,
            autodb_article_key="324:PERSIST-SUSP-1",
            autodb_supplier_id=324,
            autodb_article_number="PERSIST-SUSP-1",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="",
            evidence={"source": "test"},
        )
        ProductFitment.objects.create(
            product=self.clean,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=11,
            linkage_type="PassengerCar",
            autodb_article_key="324:PERSIST-CLEAN-1",
            supplier_id=324,
            article_number="PERSIST-CLEAN-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
            note="test",
            is_exact=False,
        )
        ProductFitment.objects.create(
            product=self.suspicious,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=12,
            linkage_type="PassengerCar",
            autodb_article_key="324:PERSIST-SUSP-1",
            supplier_id=324,
            article_number="PERSIST-SUSP-1",
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            excluded_from_public_filtering=False,
            is_stale=False,
            note="test",
            is_exact=False,
        )

    def _write_audit_csv(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "product_id",
                    "autodb_article_key",
                    "suspicious_flags",
                    "suspicious_reason",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "product_id": str(self.clean.id),
                    "autodb_article_key": "324:PERSIST-CLEAN-1",
                    "suspicious_flags": "",
                    "suspicious_reason": "",
                }
            )
            writer.writerow(
                {
                    "product_id": str(self.suspicious.id),
                    "autodb_article_key": "324:PERSIST-SUSP-1",
                    "suspicious_flags": "suspicious_link",
                    "suspicious_reason": "product_name_vs_autodb_conflict",
                }
            )

    def test_dry_run_does_not_write(self):
        with TemporaryDirectory() as tmp_dir:
            audit_csv = Path(tmp_dir) / "audit.csv"
            export_csv = Path(tmp_dir) / "export.csv"
            self._write_audit_csv(audit_csv)

            out = StringIO()
            call_command(
                "persist_autodb_fitment_quality",
                "--supplier",
                "GPL",
                "--audit-csv",
                str(audit_csv),
                "--only-trusted",
                "--dry-run",
                "--export-csv",
                str(export_csv),
                stdout=out,
            )

            clean_fitment = ProductFitment.objects.get(product=self.clean)
            suspicious_fitment = ProductFitment.objects.get(product=self.suspicious)
            self.assertEqual(clean_fitment.quality_status, ProductFitment.QUALITY_STATUS_TRUSTED)
            self.assertFalse(clean_fitment.excluded_from_public_filtering)
            self.assertEqual(suspicious_fitment.quality_status, ProductFitment.QUALITY_STATUS_TRUSTED)
            self.assertFalse(suspicious_fitment.excluded_from_public_filtering)
            self.assertIn("- fitments_changed: 1", out.getvalue())

    def test_apply_marks_suspicious_fitments_excluded(self):
        with TemporaryDirectory() as tmp_dir:
            audit_csv = Path(tmp_dir) / "audit.csv"
            export_csv = Path(tmp_dir) / "export.csv"
            self._write_audit_csv(audit_csv)

            call_command(
                "persist_autodb_fitment_quality",
                "--supplier",
                "GPL",
                "--audit-csv",
                str(audit_csv),
                "--only-trusted",
                "--apply",
                "--export-csv",
                str(export_csv),
            )

            clean_fitment = ProductFitment.objects.get(product=self.clean)
            suspicious_fitment = ProductFitment.objects.get(product=self.suspicious)
            self.assertEqual(clean_fitment.quality_status, ProductFitment.QUALITY_STATUS_TRUSTED)
            self.assertFalse(clean_fitment.excluded_from_public_filtering)
            self.assertEqual(suspicious_fitment.quality_status, ProductFitment.QUALITY_STATUS_SUSPICIOUS)
            self.assertTrue(suspicious_fitment.excluded_from_public_filtering)

            suspicious_quality = AutoDbProductLinkQuality.objects.get(
                product=self.suspicious,
                autodb_article_key="324:PERSIST-SUSP-1",
            )
            self.assertEqual(suspicious_quality.status, AutoDbProductLinkQuality.STATUS_SUSPICIOUS)
