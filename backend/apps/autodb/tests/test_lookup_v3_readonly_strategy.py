from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyService


class _FakeBrandMatcher:
    def __init__(self, *, supplier_id: int | None):
        self._supplier_id = supplier_id

    def resolve_many(self, brand_keys, source_id=None, supplier_id=None):
        del source_id, supplier_id
        key = brand_keys[0] if brand_keys else ""
        candidate = SimpleNamespace(
            supplier_id=self._supplier_id or 0,
            supplier_description="FEBI BILSTEIN",
            supplier_matchcode="FEBIBILSTEIN",
            confidence=1.0,
            reason="matchcode_exact",
        )
        result = SimpleNamespace(
            matched_supplier_id=self._supplier_id,
            reason="matchcode_exact" if self._supplier_id is not None else "brand_not_found",
            candidates=[candidate] if self._supplier_id is not None else [],
        )
        return {key: result}


class _FakeStorage:
    def __init__(self):
        self.remote_client = SimpleNamespace(sanitized_config=lambda: {"host": "localhost", "port": 3306, "database": "auto_db"})
        self.remote_exact_calls: list[tuple[str, dict[str, object]]] = []
        self.remote_like_calls = 0
        self.article_only_hit_enabled = False

    def get_local_columns(self, table):
        if table in {"article_numbers", "articles"}:
            return {"supplierId", "DataSupplierArticleNumber"}
        return set()

    def fetch_local_rows(self, *, table, filters=None, limit=100, order_by=None, columns=None):
        del table, filters, limit, order_by, columns
        return []

    def get_remote_columns(self, table):
        if table in {"article_numbers", "articles", "article_prd", "article_links"}:
            return ["supplierId", "DataSupplierArticleNumber", "productId"]
        if table == "prd":
            return ["id"]
        return []

    def fetch_remote_rows_exact(self, *, table, filters, limit=100, columns=None):
        del limit, columns
        self.remote_exact_calls.append((table, dict(filters)))
        if self.article_only_hit_enabled and table == "article_numbers":
            if "supplierId" not in filters and str(filters.get("DataSupplierArticleNumber") or "") == "01111":
                return [{"supplierId": 101, "DataSupplierArticleNumber": "01111"}]
        return []

    def fetch_remote_rows_in(self, *, table, column, values, extra_filters=None, limit=1000, columns=None):
        del table, column, values, extra_filters, limit, columns
        return []

    def fetch_remote_rows_like(self, *args, **kwargs):
        del args, kwargs
        self.remote_like_calls += 1
        return []


class AutoDbLookupV3ReadOnlyStrategyTests(SimpleTestCase):
    def test_cascade_starts_with_supplier_plus_normalized_and_never_uses_like(self):
        storage = _FakeStorage()
        matcher = _FakeBrandMatcher(supplier_id=101)
        service = AutoDbLookupV3ReadOnlyService(storage=storage, brand_matcher=matcher)

        result = service.lookup(brand="FEBI BILSTEIN", article="ABC-123")

        self.assertFalse(result.found)
        self.assertGreaterEqual(len(storage.remote_exact_calls), 1)
        first_table, first_filters = storage.remote_exact_calls[0]
        self.assertEqual(first_table, "article_numbers")
        self.assertEqual(first_filters.get("supplierId"), 101)
        self.assertEqual(first_filters.get("DataSupplierArticleNumber"), "ABC123")
        self.assertEqual(storage.remote_like_calls, 0)

    def test_article_only_step_can_find_hit_and_return_supplier_from_row(self):
        storage = _FakeStorage()
        storage.article_only_hit_enabled = True
        matcher = _FakeBrandMatcher(supplier_id=None)
        service = AutoDbLookupV3ReadOnlyService(storage=storage, brand_matcher=matcher)

        result = service.lookup(brand="FEBI BILSTEIN", article="01111")

        self.assertTrue(result.found)
        self.assertEqual(result.supplier_id, 101)
        self.assertIn("B_norm_article_only:remote:article_numbers.DataSupplierArticleNumber", result.matched_source)
        self.assertEqual(storage.remote_like_calls, 0)
