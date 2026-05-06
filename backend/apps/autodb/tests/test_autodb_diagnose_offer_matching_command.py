from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.autodb.services.raw_offer_enrichment import PairBucket, PairResolution
from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportRun, ImportSource, SupplierRawOffer


class AutoDbDiagnoseOfferMatchingCommandTests(TestCase):
    def setUp(self):
        supplier = Supplier.objects.create(name="GPL", code="gpl", is_active=True)
        source = ImportSource.objects.create(
            code="gpl",
            name="GPL",
            supplier=supplier,
            parser_type=ImportSource.PARSER_GPL,
            input_path="",
            is_active=True,
        )
        run = ImportRun.objects.create(source=source)
        SupplierRawOffer.objects.create(
            run=run,
            source=source,
            supplier=supplier,
            external_sku="820099",
            article="820099",
            normalized_article="820099",
            brand_name="AUTEX",
            normalized_brand="AUTEX",
            product_name="AUTEX 820099",
            stock_qty=1,
        )

    @patch("apps.supplier_imports.services.integrations.utr.client.UtrClient")
    @patch("apps.autodb.management.commands.autodb_diagnose_offer_matching.Command._top_brands", return_value=[])
    @patch("apps.autodb.management.commands.autodb_diagnose_offer_matching.AutoDbRawOfferEnrichmentService._resolve_local_chunk")
    def test_command_prints_summary_and_does_not_call_utr(self, resolve_local_mock, _brand_matcher, utr_cls):
        resolve_local_mock.return_value = [
            PairResolution(
                bucket=PairBucket(
                    normalized_brand="AUTEX",
                    normalized_article="820099",
                    sample_brand="AUTEX",
                    sample_article="820099",
                    article_variants=("820099",),
                ),
                supplier_id=300,
                article_key="300:820099",
                reason="matched_local",
                source="local",
            )
        ]

        out = StringIO()
        call_command("autodb_diagnose_offer_matching", "--supplier", "GPL", "--limit", "10", stdout=out)

        output = out.getvalue()
        self.assertIn("total raw offers: 1", output)
        self.assertIn("found count: 1", output)
        self.assertIn("UTR calls: 0", output)
        utr_cls.assert_not_called()
