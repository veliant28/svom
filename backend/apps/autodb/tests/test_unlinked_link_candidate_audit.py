from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.autodb.services.unlinked_link_candidate_audit import UnlinkedLinkCandidateAuditService


class _FakeStorage:
    def get_local_columns(self, table):
        return set()

    def get_remote_columns(self, table):
        return []


class _FakeMatcher:
    def resolve_many(self, brands, source_id=None, supplier_id=None):
        return {}


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
