from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher


class SupplierBrandMatcherTests(SimpleTestCase):
    def _matcher(self):
        storage = Mock()
        storage.ensure_table.return_value = None
        storage.fetch_local_rows.return_value = [
            {"id": 300, "description": "AUTEX", "matchcode": "AUTEX", "fulldescription": "AUTEX"},
            {"id": 301, "description": "MANN-FILTER", "matchcode": "MANNFILTER", "fulldescription": "MANN FILTER"},
        ]
        return SupplierBrandMatcher(storage=storage)

    def test_exact_matchcode_match(self):
        matcher = self._matcher()
        with patch.object(matcher, "_load_aliases", return_value={}):
            with patch.object(matcher, "_load_autodb_aliases", return_value={}):
                result = matcher.resolve_many(["AUTEX"])

        self.assertEqual(result["AUTEX"].matched_supplier_id, 300)
        self.assertEqual(result["AUTEX"].reason, "matchcode_exact")

    def test_description_relaxed_match(self):
        matcher = self._matcher()
        with patch.object(matcher, "_load_aliases", return_value={}):
            with patch.object(matcher, "_load_autodb_aliases", return_value={}):
                result = matcher.resolve_many(["MANNFILTER"])

        self.assertEqual(result["MANNFILTER"].matched_supplier_id, 301)

    def test_alias_match(self):
        matcher = self._matcher()
        with patch.object(matcher, "_load_suppliers", return_value=[{"id": 9, "description": "MAHLE", "matchcode": "MAHLE"}]):
            with patch.object(matcher, "_load_aliases", return_value={"MAHLEKNECHT": "MAHLE"}):
                with patch.object(matcher, "_load_autodb_aliases", return_value={}):
                    result = matcher.resolve_many(["MAHLE-KNECHT"])

        self.assertEqual(result["MAHLEKNECHT"].matched_supplier_id, 9)
        self.assertTrue(result["MAHLEKNECHT"].reason.startswith("alias:"))

    def test_autodb_manual_alias_has_priority(self):
        matcher = self._matcher()
        with patch.object(matcher, "_load_aliases", return_value={}):
            with patch.object(
                matcher,
                "_load_autodb_aliases",
                return_value={"WIXFILTERS": {"autodb_supplier_id": 300, "confidence": 1.0, "manual_confirmed": True}},
            ):
                result = matcher.resolve_many(["WIX FILTERS"])

        self.assertEqual(result["WIXFILTERS"].matched_supplier_id, 300)
        self.assertEqual(result["WIXFILTERS"].reason, "manual_alias")
