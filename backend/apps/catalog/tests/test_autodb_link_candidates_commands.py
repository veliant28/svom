from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management.base import CommandError
from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import AutoDbProductLinkQuality, Brand, Category, Product, ProductImage
from apps.pricing.models import Supplier, SupplierOffer
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbLinkCandidatesCommandsTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="TEST", slug="test", is_active=True)
        self.category = Category.objects.create(
            name="Резонатор",
            slug="rezonator-test",
            is_active=True,
            is_assignable=True,
        )
        self.supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        self.source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="/tmp/none",
            is_active=True,
        )
        self.run = ImportRun.objects.create(source=self.source, status=ImportRun.STATUS_SUCCESS, trigger="test", dry_run=False)
        self.product = Product.objects.create(
            sku="GPL-T-001",
            article="T-001",
            name="Резонатор TEST",
            slug="rezonator-test-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.raw_offer = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="T-001",
            article="T-001",
            normalized_article="T001",
            brand_name="TEST",
            normalized_brand="TEST",
            product_name="Резонатор TEST",
            currency="UAH",
            price="100.00",
            stock_qty=1,
            matched_product=self.product,
            raw_payload={
                "Категорія": "Резонатори",
                "Група ТД": "TEST",
                "Найменування": "Резонатор TEST",
                "Зображення товару": "https://cdn.example.com/g1.webp",
            },
            is_valid=True,
        )
        self.offer = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_sku="T-001",
            currency="UAH",
            purchase_price="100.00",
            stock_qty=1,
            is_available=True,
        )

    def _build_candidates_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "supplier_raw_offer_id",
                    "supplier_offer_id",
                    "raw_brand",
                    "raw_article",
                    "raw_name",
                    "raw_category",
                    "raw_group",
                    "mapped_site_category",
                    "gpl_image_url",
                    "candidate_autodb_supplier_id",
                    "candidate_autodb_article_number",
                    "candidate_autodb_title",
                    "candidate_autodb_group",
                    "brand_match_score",
                    "article_match_score",
                    "semantic_score",
                    "category_compatibility_score",
                    "decision",
                    "reason",
                    "blocker_type",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _base_candidate_row(self, *, product: Product, raw_offer: SupplierRawOffer, offer: SupplierOffer) -> dict[str, str]:
        return {
            "product_id": str(product.id),
            "supplier_raw_offer_id": str(raw_offer.id),
            "supplier_offer_id": str(offer.id),
            "raw_brand": "TEST",
            "raw_article": str(product.article or ""),
            "raw_name": str(product.name or ""),
            "raw_category": "Резонатори",
            "raw_group": "TEST",
            "mapped_site_category": "Резонатор",
            "gpl_image_url": "https://cdn.example.com/g1.webp",
            "candidate_autodb_supplier_id": "22",
            "candidate_autodb_article_number": str(product.article or ""),
            "candidate_autodb_title": "Резонатор",
            "candidate_autodb_group": "Exhaust",
            "brand_match_score": "1.000",
            "article_match_score": "1.000",
            "semantic_score": "1.000",
            "category_compatibility_score": "1.000",
            "decision": "safe_link_candidate",
            "reason": "exact_article_and_category_compatible",
            "blocker_type": "",
        }

    @patch("apps.catalog.management.commands.audit_autodb_link_candidates_after_gpl_import.AutoDbArticleLookupService.lookup")
    @patch("apps.catalog.management.commands.audit_autodb_link_candidates_after_gpl_import.Command._find_local_article_row")
    def test_audit_command_exports_required_columns_and_semantic_blocker(self, find_row_mock, lookup_mock):
        lookup_mock.return_value = SimpleNamespace(
            found=True,
            supplier_id=22,
            canonical_article_number="T-001",
            canonical_brand="TEST",
        )
        find_row_mock.return_value = {
            "NormalizedDescription": "Амортизатор передній",
            "GenericArticleDescription": "Shock absorber",
        }

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "audit.csv"
            out = StringIO()
            call_command(
                "audit_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--limit",
                "20000",
                "--export-csv",
                str(path),
                stdout=out,
            )

            self.assertTrue(path.exists())
            rows = list(csv.DictReader(path.open(encoding="utf-8")))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["supplier_raw_offer_id"], str(self.raw_offer.id))
            self.assertEqual(row["supplier_offer_id"], str(self.offer.id))
            self.assertEqual(row["decision"], "semantic_conflict")
            self.assertIn("exhaust_vs_shock", row["blocker_type"])
            self.assertEqual(row["raw_group"], "TEST")
            self.assertEqual(row["raw_brand_source_field"], "raw_payload.Група ТД")
            self.assertEqual(row["article_source_field"], "supplier_raw_offer.article")
            self.assertEqual(row["lookup_article"], "T-001")
            self.assertIn("UTR calls=0", out.getvalue())
            self.assertIn("writes=0", out.getvalue())

    @patch("apps.catalog.management.commands.audit_autodb_link_candidates_after_gpl_import.AutoDbArticleLookupService.lookup")
    @patch("apps.catalog.management.commands.audit_autodb_link_candidates_after_gpl_import.Command._find_local_article_row")
    def test_audit_uses_td_article_priority_and_never_uses_code(self, find_row_mock, lookup_mock):
        lookup_mock.return_value = SimpleNamespace(
            found=False,
            supplier_id=None,
            canonical_article_number="",
            canonical_brand="",
        )
        find_row_mock.return_value = {}
        self.raw_offer.raw_payload = {
            "Код": "GPL-CODE-777",
            "Артикул": "SUP-ART-001",
            "Артикул ТД": "TD-ART-999",
            "Група ТД": "BRAND-TD",
            "Категорія": "Резонатори",
        }
        self.raw_offer.article = "MODEL-ARTICLE-ROW"
        self.raw_offer.brand_name = "RAW-BRAND"
        self.raw_offer.save(update_fields=["raw_payload", "article", "brand_name", "updated_at"])

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "audit_td.csv"
            out = StringIO()
            call_command(
                "audit_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--limit",
                "10",
                "--article-source",
                "td_article",
                "--export-csv",
                str(path),
                stdout=out,
            )

            row = list(csv.DictReader(path.open(encoding="utf-8")))[0]
            self.assertEqual(row["raw_brand"], "BRAND-TD")
            self.assertEqual(row["raw_brand_source_field"], "raw_payload.Група ТД")
            self.assertEqual(row["article_source_field"], "raw_payload.Артикул ТД")
            self.assertEqual(row["lookup_article"], "TD-ART-999")
            self.assertEqual(row["gpl_code"], "GPL-CODE-777")
            self.assertEqual(row["gpl_article"], "SUP-ART-001")
            self.assertEqual(row["gpl_td_article"], "TD-ART-999")
            lookup_mock.assert_called_once_with(
                brand_name="BRAND-TD",
                article="TD-ART-999",
                allow_remote=False,
            )
            self.assertNotIn("GPL-CODE-777", out.getvalue())

    @patch("apps.catalog.management.commands.audit_autodb_link_candidates_after_gpl_import.AutoDbArticleLookupService.lookup")
    @patch("apps.catalog.management.commands.audit_autodb_link_candidates_after_gpl_import.Command._find_local_article_row")
    def test_audit_falls_back_to_gpl_article_when_td_article_empty(self, find_row_mock, lookup_mock):
        lookup_mock.return_value = SimpleNamespace(
            found=False,
            supplier_id=None,
            canonical_article_number="",
            canonical_brand="",
        )
        find_row_mock.return_value = {}
        self.raw_offer.raw_payload = {
            "Код": "GPL-CODE-001",
            "Артикул": "SUP-ART-777",
            "Артикул ТД": "",
            "Група ТД": "BRAND-TD",
        }
        self.raw_offer.article = "MODEL-ARTICLE-ROW"
        self.raw_offer.save(update_fields=["raw_payload", "article", "updated_at"])

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "audit_fallback.csv"
            call_command(
                "audit_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--limit",
                "10",
                "--article-source",
                "td_article",
                "--export-csv",
                str(path),
            )

            row = list(csv.DictReader(path.open(encoding="utf-8")))[0]
            self.assertEqual(row["article_source_field"], "raw_payload.Артикул")
            self.assertEqual(row["lookup_article"], "SUP-ART-777")
            lookup_mock.assert_called_once_with(
                brand_name="BRAND-TD",
                article="SUP-ART-777",
                allow_remote=False,
            )

    def test_apply_command_dry_run_is_read_only_and_does_not_change_name_category_image(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://cdn.example.com/g1.webp",
            source=ProductImage.SOURCE_GPL_PRICE,
            is_primary=True,
            sort_order=0,
        )

        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export = Path(tmp_dir) / "apply.csv"
            self._build_candidates_csv(
                candidates,
                [self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)],
            )

            before = Product.objects.get(id=self.product.id)
            before_quality = AutoDbProductLinkQuality.objects.count()
            out = StringIO()
            call_command(
                "apply_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--candidates-csv",
                str(candidates),
                "--only-safe",
                "--dry-run",
                "--export-csv",
                str(export),
                stdout=out,
            )

            after = Product.objects.get(id=self.product.id)
            self.assertEqual(before.name, after.name)
            self.assertEqual(before.category_id, after.category_id)
            self.assertEqual(before.autodb_article_key, after.autodb_article_key)
            self.assertEqual(before_quality, AutoDbProductLinkQuality.objects.count())
            self.assertTrue(export.exists())
            rows = list(csv.DictReader(export.open(encoding="utf-8")))
            self.assertEqual(rows[0]["action"], "would_link")
            self.assertEqual(rows[0]["would_change_name"], "0")
            self.assertEqual(rows[0]["would_change_category"], "0")
            self.assertEqual(rows[0]["would_change_primary_image"], "0")
            self.assertIn("would_change_name: 0", out.getvalue())
            self.assertIn("price/stock changed=0", out.getvalue())
            self.assertIn("UTR calls=0", out.getvalue())

    def test_apply_command_requires_explicit_mode(self):
        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export = Path(tmp_dir) / "apply.csv"
            self._build_candidates_csv(
                candidates,
                [self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)],
            )

            with self.assertRaises(CommandError):
                call_command(
                    "apply_autodb_link_candidates_after_gpl_import",
                    "--supplier",
                    "GPL",
                    "--candidates-csv",
                    str(candidates),
                    "--only-safe",
                    "--export-csv",
                    str(export),
                )

    def test_apply_command_requires_only_safe_flag(self):
        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export = Path(tmp_dir) / "apply.csv"
            self._build_candidates_csv(
                candidates,
                [self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)],
            )

            with self.assertRaises(CommandError):
                call_command(
                    "apply_autodb_link_candidates_after_gpl_import",
                    "--supplier",
                    "GPL",
                    "--candidates-csv",
                    str(candidates),
                    "--dry-run",
                    "--export-csv",
                    str(export),
                )

            with self.assertRaises(CommandError):
                call_command(
                    "apply_autodb_link_candidates_after_gpl_import",
                    "--supplier",
                    "GPL",
                    "--candidates-csv",
                    str(candidates),
                    "--only-safe",
                    "--dry-run",
                    "--apply",
                    "--export-csv",
                    str(export),
                )

    def test_apply_limit_is_deterministic_and_repeat_dry_run_marks_already_linked(self):
        product2 = Product.objects.create(
            sku="GPL-T-002",
            article="T-002",
            name="Резонатор TEST 2",
            slug="rezonator-test-product-2",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        raw_offer2 = SupplierRawOffer.objects.create(
            run=self.run,
            source=self.source,
            supplier=self.supplier,
            external_sku="T-002",
            article="T-002",
            normalized_article="T002",
            brand_name="TEST",
            normalized_brand="TEST",
            product_name="Резонатор TEST 2",
            currency="UAH",
            price="120.00",
            stock_qty=2,
            matched_product=product2,
            raw_payload={"Категорія": "Резонатори", "Група ТД": "TEST"},
            is_valid=True,
        )
        offer2 = SupplierOffer.objects.create(
            supplier=self.supplier,
            product=product2,
            supplier_sku="T-002",
            currency="UAH",
            purchase_price="120.00",
            stock_qty=2,
            is_available=True,
        )

        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export_apply = Path(tmp_dir) / "apply_real.csv"
            export_repeat = Path(tmp_dir) / "apply_repeat.csv"
            self._build_candidates_csv(
                candidates,
                [
                    self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer),
                    self._base_candidate_row(product=product2, raw_offer=raw_offer2, offer=offer2),
                ],
            )

            out_apply = StringIO()
            call_command(
                "apply_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--candidates-csv",
                str(candidates),
                "--only-safe",
                "--limit",
                "1",
                "--apply",
                "--export-csv",
                str(export_apply),
                stdout=out_apply,
            )

            first = Product.objects.get(id=self.product.id)
            second = Product.objects.get(id=product2.id)
            self.assertEqual(first.autodb_article_key, "22:T-001")
            self.assertEqual(second.autodb_article_key, "")
            self.assertEqual(AutoDbProductLinkQuality.objects.filter(product=self.product, status="trusted").count(), 1)
            self.assertIn("selected_for_run: 1", out_apply.getvalue())
            self.assertIn("applied_links: 1", out_apply.getvalue())
            self.assertIn("skipped_by_limit: 1", out_apply.getvalue())

            out_repeat = StringIO()
            call_command(
                "apply_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--candidates-csv",
                str(candidates),
                "--only-safe",
                "--limit",
                "1",
                "--dry-run",
                "--export-csv",
                str(export_repeat),
                stdout=out_repeat,
            )
            self.assertIn("selected_for_run: 1", out_repeat.getvalue())
            self.assertIn("would_link: 0", out_repeat.getvalue())
            self.assertIn("skipped_already_complete_link: 1", out_repeat.getvalue())

    def test_real_apply_changes_only_autodb_link_fields(self):
        ProductImage.objects.create(
            product=self.product,
            image=None,
            remote_url="https://cdn.example.com/g1.webp",
            source=ProductImage.SOURCE_GPL_PRICE,
            is_primary=True,
            sort_order=0,
        )
        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export = Path(tmp_dir) / "apply_real.csv"
            self._build_candidates_csv(
                candidates,
                [self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)],
            )

            before = Product.objects.get(id=self.product.id)
            before_name = before.name
            before_category = before.category_id
            before_images = list(ProductImage.objects.filter(product=self.product).values_list("remote_url", "is_primary", "source"))

            call_command(
                "apply_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--candidates-csv",
                str(candidates),
                "--only-safe",
                "--apply",
                "--export-csv",
                str(export),
            )

            after = Product.objects.get(id=self.product.id)
            after_images = list(ProductImage.objects.filter(product=self.product).values_list("remote_url", "is_primary", "source"))
            self.assertEqual(after.name, before_name)
            self.assertEqual(after.category_id, before_category)
            self.assertEqual(before_images, after_images)
            self.assertEqual(after.autodb_supplier_id, 22)
            self.assertEqual(after.autodb_article_number, "T-001")
            self.assertEqual(after.autodb_article_key, "22:T-001")
            self.assertEqual(
                AutoDbProductLinkQuality.objects.filter(
                    product=self.product,
                    autodb_article_key="22:T-001",
                    status=AutoDbProductLinkQuality.STATUS_TRUSTED,
                ).count(),
                1,
            )

    def test_apply_summary_separates_new_vs_incomplete_link_updates(self):
        self.product.autodb_supplier_id = 22
        self.product.autodb_article_number = ""
        self.product.autodb_article_key = ""
        self.product.save(update_fields=["autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"])

        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export = Path(tmp_dir) / "apply_real.csv"
            self._build_candidates_csv(
                candidates,
                [self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)],
            )

            out = StringIO()
            call_command(
                "apply_autodb_link_candidates_after_gpl_import",
                "--supplier",
                "GPL",
                "--candidates-csv",
                str(candidates),
                "--only-safe",
                "--apply",
                "--export-csv",
                str(export),
                stdout=out,
            )
            output = out.getvalue()
            self.assertIn("created_new_links: 0", output)
            self.assertIn("updated_incomplete_link_fields: 1", output)

    def test_diagnose_link_state_reports_safe_and_not_safe_linked_rows(self):
        self.product.autodb_supplier_id = 22
        self.product.autodb_article_number = "T-001"
        self.product.autodb_article_key = "22:T-001"
        self.product.save(update_fields=["autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"])
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="22:T-001",
            autodb_supplier_id=22,
            autodb_article_number="T-001",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="seed_trusted",
        )

        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export = Path(tmp_dir) / "diagnose.csv"
            summary = Path(tmp_dir) / "summary.csv"
            row = self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)
            row["decision"] = "needs_review"
            row["reason"] = "category_compatibility_low"
            self._build_candidates_csv(candidates, [row])

            out = StringIO()
            call_command(
                "diagnose_autodb_link_state",
                "--supplier",
                "GPL",
                "--latest-candidates-csv",
                str(candidates),
                "--export-csv",
                str(export),
                "--summary-csv",
                str(summary),
                stdout=out,
            )

            self.assertTrue(export.exists())
            self.assertTrue(summary.exists())
            summary_rows = {item["metric"]: int(item["value"]) for item in csv.DictReader(summary.open(encoding="utf-8"))}
            self.assertEqual(summary_rows["linked_by_key"], 1)
            self.assertEqual(summary_rows["complete_link_fields"], 1)
            self.assertEqual(summary_rows["linked_not_safe_in_latest_audit"], 1)
            self.assertIn("writes=0", out.getvalue())
            self.assertIn("UTR calls=0", out.getvalue())

    def test_reconcile_link_quality_marks_not_safe_as_needs_review_without_unlink(self):
        self.product.autodb_supplier_id = 22
        self.product.autodb_article_number = "T-001"
        self.product.autodb_article_key = "22:T-001"
        self.product.save(update_fields=["autodb_supplier_id", "autodb_article_number", "autodb_article_key", "updated_at"])
        AutoDbProductLinkQuality.objects.create(
            product=self.product,
            autodb_article_key="22:T-001",
            autodb_supplier_id=22,
            autodb_article_number="T-001",
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            reason="seed_trusted",
        )

        with TemporaryDirectory() as tmp_dir:
            candidates = Path(tmp_dir) / "candidates.csv"
            export_dry = Path(tmp_dir) / "reconcile_dry.csv"
            export_real = Path(tmp_dir) / "reconcile_real.csv"
            row = self._base_candidate_row(product=self.product, raw_offer=self.raw_offer, offer=self.offer)
            row["decision"] = "needs_review"
            row["reason"] = "category_compatibility_low"
            self._build_candidates_csv(candidates, [row])

            out_dry = StringIO()
            call_command(
                "reconcile_autodb_link_quality_with_latest_audit",
                "--supplier",
                "GPL",
                "--latest-candidates-csv",
                str(candidates),
                "--dry-run",
                "--export-csv",
                str(export_dry),
                stdout=out_dry,
            )
            self.assertIn("would_mark_needs_review: 1", out_dry.getvalue())
            self.assertIn("would_unlink: 0", out_dry.getvalue())

            out_real = StringIO()
            call_command(
                "reconcile_autodb_link_quality_with_latest_audit",
                "--supplier",
                "GPL",
                "--latest-candidates-csv",
                str(candidates),
                "--apply",
                "--export-csv",
                str(export_real),
                stdout=out_real,
            )
            self.assertIn("marked_needs_review: 1", out_real.getvalue())
            quality = AutoDbProductLinkQuality.objects.get(product=self.product, autodb_article_key="22:T-001")
            self.assertEqual(quality.status, AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW)
            self.assertTrue(str(quality.reason).startswith("latest_audit_"))
            refreshed = Product.objects.get(id=self.product.id)
            self.assertEqual(refreshed.autodb_article_key, "22:T-001")
