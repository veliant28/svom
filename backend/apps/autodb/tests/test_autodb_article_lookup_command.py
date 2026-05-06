from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.autodb.services.local_db_readiness import LocalAutoDbReadinessResult
from apps.autodb.services.article_lookup import ArticleLookupResult


class AutoDbArticleLookupCommandTests(SimpleTestCase):
    @patch(
        "apps.autodb.management.commands.autodb_article_lookup.wait_for_local_autodb_ready",
        return_value=LocalAutoDbReadinessResult(
            ready=True,
            reason="ready",
            error_message="",
            host="127.0.0.1",
            port="5434",
            database="Auto_DB_Pro",
            attempts=1,
            waited_seconds=0.0,
        ),
    )
    @patch("apps.autodb.management.commands.autodb_article_lookup.AutoDbArticleLookupService.lookup")
    def test_command_prints_lookup_result(self, lookup_mock, _ready_mock):
        lookup_mock.return_value = ArticleLookupResult(
            found=True,
            normalized_brand="BOSCH",
            normalized_article="W71295",
            supplier_id=100,
            article_key="100:W712/95",
            article_id=200,
            canonical_article_number="W712/95",
            canonical_brand="BOSCH",
            supplier_source="local",
            article_source="remote",
            populated_tables={"article_numbers": 1},
            warnings=[],
        )
        out = StringIO()

        call_command("autodb_article_lookup", "--brand", "Bosch", "--article", "W712/95", stdout=out)

        output = out.getvalue()
        self.assertIn("found: True", output)
        self.assertIn("supplier_id: 100", output)
        self.assertIn("article_id: 200", output)
        self.assertIn("article_key: 100:W712/95", output)
