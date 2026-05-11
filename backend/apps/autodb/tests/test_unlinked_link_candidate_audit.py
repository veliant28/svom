from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.autodb.services.unlinked_link_candidate_audit import UnlinkedLinkCandidateAuditService


class _FakeStorage:
    def __init__(self):
        self.rows_by_table: dict[str, list[dict]] = {
            "article_numbers": [],
            "articles": [],
            "suppliers": [],
        }
        self.local_calls: list[tuple[str, dict]] = []
        self.remote_calls: list[tuple[str, dict]] = []

    def get_local_columns(self, table):
        mapping = {
            "article_numbers": {"supplierId", "DataSupplierArticleNumber", "Description"},
            "articles": {"supplierId", "DataSupplierArticleNumber", "Description"},
            "suppliers": {"id", "description", "matchcode", "fulldescription"},
        }
        return mapping.get(table, set())

    def get_remote_columns(self, table):
        return []

    def fetch_local_rows(self, *, table, filters=None, limit=100, order_by=None, columns=None):
        filters = filters or {}
        self.local_calls.append((table, dict(filters)))
        rows = []
        for row in self.rows_by_table.get(table, []):
            ok = True
            for key, value in filters.items():
                if row.get(key) != value:
                    ok = False
                    break
            if ok:
                rows.append(dict(row))
        rows = rows[: max(int(limit), 1)]
        if columns:
            selected = []
            for row in rows:
                selected.append({col: row.get(col) for col in columns})
            return selected
        return rows

    def fetch_remote_rows_exact(self, *, table, filters, limit=100, columns=None):  # pragma: no cover - explicit guard
        self.remote_calls.append((table, dict(filters)))
        return []

    def fetch_remote_rows_like(self, *, table, column, value, limit=100):  # pragma: no cover - explicit guard
        self.remote_calls.append((table, {column: value}))
        return []


class _FakeMatcher:
    def __init__(self, *, supplier_id: int = 110, reason: str = "matchcode_exact"):
        self.supplier_id = supplier_id
        self.reason = reason

    def resolve_many(self, brands, source_id=None, supplier_id=None):
        out = {}
        for brand in brands:
            candidate = SimpleNamespace(
                supplier_id=self.supplier_id,
                supplier_description="NTN-SNR",
                supplier_matchcode="NTN-SNR",
                confidence=1.0,
                reason=self.reason,
            )
            out[brand] = SimpleNamespace(
                raw_brand=brand,
                normalized_brand=brand,
                matched_supplier_id=self.supplier_id,
                confidence=1.0,
                reason=self.reason,
                candidates=(candidate,),
            )
        return out


class _FakeResolver:
    def resolve(self, *, raw_payload, article, external_sku):
        return SimpleNamespace(manufacturer_article=article)


class UnlinkedLinkCandidateAuditServiceTests(SimpleTestCase):
    def test_semantic_conflict_non_auto_brand(self):
        service = UnlinkedLinkCandidateAuditService(
            storage=_FakeStorage(),
            brand_matcher=_FakeMatcher(),
            gpl_resolver=_FakeResolver(),
        )

        row = service.audit_offer(
            product_id="p1",
            raw_offer_id="r1",
            product_name="Емаль аерозоль MITKA чорна",
            display_brand="MITKA",
            brand_source="supplier_fallback",
            raw_brand="MITKA",
            raw_payload={"Найменування": "Емаль аерозоль чорна", "Категорія": "Автохімія"},
            raw_article="M-001",
            external_sku="M-001",
            allow_remote=False,
            source_id=None,
            supplier_id=None,
        )

        self.assertEqual(row.semantic_status, "conflict")
        self.assertEqual(row.recommendation, "non_auto_or_supplier_only")

    def test_v3_blank_raw_article_uses_deterministic_canonical_remote_lookup(self):
        storage = _FakeStorage()
        storage.rows_by_table["article_numbers"] = [
            {
                "supplierId": 110,
                "DataSupplierArticleNumber": "R174.52",
                "Description": "Wheel bearing",
            }
        ]
        storage.rows_by_table["articles"] = [
            {
                "supplierId": 110,
                "DataSupplierArticleNumber": "R174.52",
                "Description": "Wheel bearing article",
            }
        ]
        service = UnlinkedLinkCandidateAuditService(
            storage=storage,
            brand_matcher=_FakeMatcher(supplier_id=110),
            gpl_resolver=_FakeResolver(),
        )

        row = service.audit_offer(
            product_id="p-v3",
            raw_offer_id="r-v3",
            product_name="Підшипник маточини",
            display_brand="NTN-SNR",
            brand_source="supplier_fallback",
            raw_brand="NTN-SNR",
            raw_payload={"Категорія": "Підвіска", "stock": 0},
            raw_article="",
            external_sku="",
            allow_remote=False,
            source_id=None,
            supplier_id=None,
            canonical_article="R17452",
            remote_stored_article="R174.52",
            mapped_supplier_id=110,
            deterministic_exact_only=True,
        )

        self.assertEqual(row.article_numbers_table_match, "yes")
        self.assertEqual(row.proposed_autodb_supplier_id, "110")
        self.assertEqual(row.proposed_autodb_article_number, "R174.52")
        self.assertEqual(row.recommendation, "safe_auto_link_candidate")
        self.assertEqual(row.reason, "local_exact_remote_stored_article_candidate")

    def test_clone_linkage_present_with_deterministic_lookup_is_not_article_not_found(self):
        storage = _FakeStorage()
        storage.rows_by_table["article_numbers"] = [
            {"supplierId": 110, "DataSupplierArticleNumber": "KBLF41082", "Description": "Hub bearing"}
        ]
        storage.rows_by_table["articles"] = [
            {"supplierId": 110, "DataSupplierArticleNumber": "KBLF41082", "Description": "Hub bearing article"}
        ]
        service = UnlinkedLinkCandidateAuditService(
            storage=storage,
            brand_matcher=_FakeMatcher(supplier_id=110),
            gpl_resolver=_FakeResolver(),
        )

        row = service.audit_offer(
            product_id="p-linkage",
            raw_offer_id="r-linkage",
            product_name="Підшипник маточини",
            display_brand="NTN-SNR",
            brand_source="supplier_fallback",
            raw_brand="NTN-SNR",
            raw_payload={},
            raw_article="",
            external_sku="",
            allow_remote=False,
            source_id=None,
            supplier_id=None,
            canonical_article="KBLF41082",
            remote_stored_article="KBLF41082",
            mapped_supplier_id=110,
            deterministic_exact_only=True,
        )

        self.assertEqual(row.article_numbers_table_match, "yes")
        self.assertNotEqual(row.reason, "local_supplier_candidate_found_article_not_matched")

    def test_stock_zero_does_not_block_safe_classification(self):
        storage = _FakeStorage()
        storage.rows_by_table["article_numbers"] = [
            {"supplierId": 110, "DataSupplierArticleNumber": "R180.08", "Description": "Hub bearing"}
        ]
        service = UnlinkedLinkCandidateAuditService(
            storage=storage,
            brand_matcher=_FakeMatcher(supplier_id=110),
            gpl_resolver=_FakeResolver(),
        )

        row = service.audit_offer(
            product_id="p-stock",
            raw_offer_id="r-stock",
            product_name="Підшипник",
            display_brand="NTN-SNR",
            brand_source="supplier_fallback",
            raw_brand="NTN-SNR",
            raw_payload={"stock": 0},
            raw_article="",
            external_sku="",
            allow_remote=False,
            source_id=None,
            supplier_id=None,
            canonical_article="R18008",
            remote_stored_article="R180.08",
            mapped_supplier_id=110,
            deterministic_exact_only=True,
        )

        self.assertEqual(row.recommendation, "safe_auto_link_candidate")
        self.assertGreaterEqual(row.confidence, 0.95)

    def test_deterministic_mode_avoids_external_sku_and_name_search(self):
        storage = _FakeStorage()
        storage.rows_by_table["article_numbers"] = [
            {"supplierId": 110, "DataSupplierArticleNumber": "ABC-123", "Description": "Part"}
        ]
        service = UnlinkedLinkCandidateAuditService(
            storage=storage,
            brand_matcher=_FakeMatcher(supplier_id=110),
            gpl_resolver=_FakeResolver(),
        )

        row = service.audit_offer(
            product_id="p-no-fuzzy",
            raw_offer_id="r-no-fuzzy",
            product_name="Підшипник ZZ999",
            display_brand="NTN-SNR",
            brand_source="supplier_fallback",
            raw_brand="NTN-SNR",
            raw_payload={"Найменування": "Підшипник ZZ999", "Код": "EXT-001"},
            raw_article="",
            external_sku="EXT-001",
            allow_remote=False,
            source_id=None,
            supplier_id=None,
            canonical_article="ABC123",
            remote_stored_article="ABC-123",
            mapped_supplier_id=110,
            deterministic_exact_only=True,
        )

        looked_up_articles = []
        for table, filters in storage.local_calls:
            if table not in {"article_numbers", "articles"}:
                continue
            value = filters.get("DataSupplierArticleNumber")
            if value:
                looked_up_articles.append(str(value))

        looked_up_text = " ".join(looked_up_articles)
        self.assertNotIn("EXT-001", looked_up_text)
        self.assertNotIn("ZZ999", looked_up_text)
        self.assertEqual(storage.remote_calls, [])
        self.assertEqual(row.recommendation, "safe_auto_link_candidate")

    def test_existing_safe_candidate_behavior_unchanged(self):
        storage = _FakeStorage()
        storage.rows_by_table["article_numbers"] = [
            {"supplierId": 110, "DataSupplierArticleNumber": "KBLF41801", "Description": "Part"}
        ]
        service = UnlinkedLinkCandidateAuditService(
            storage=storage,
            brand_matcher=_FakeMatcher(supplier_id=110),
            gpl_resolver=_FakeResolver(),
        )

        row = service.audit_offer(
            product_id="p-safe",
            raw_offer_id="r-safe",
            product_name="Підшипник маточини",
            display_brand="NTN-SNR",
            brand_source="supplier_fallback",
            raw_brand="NTN-SNR",
            raw_payload={"Артикул ТД": "KBLF41801"},
            raw_article="KBLF41801",
            external_sku="",
            allow_remote=False,
            source_id=None,
            supplier_id=None,
        )

        self.assertEqual(row.recommendation, "safe_auto_link_candidate")
        self.assertEqual(row.reason, "local_exact_manufacturer_article_candidate")
