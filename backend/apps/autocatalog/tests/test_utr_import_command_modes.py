from django.test import SimpleTestCase

from apps.autocatalog.application.utr_import_command.modes import merge_detail_ids


class UtrImportCommandModesTests(SimpleTestCase):
    def test_merge_detail_ids_can_keep_only_missing_applicability_before_limit(self):
        detail_ids = merge_detail_ids(
            product_detail_ids=["300", "100"],
            mapped_detail_ids=["100", "200", "400"],
            existing_map_detail_ids=["100", "300"],
            missing_applicability_only=True,
            limit=1,
            offset=0,
        )

        self.assertEqual(detail_ids, ["200"])

    def test_merge_detail_ids_keeps_existing_behavior_without_missing_filter(self):
        detail_ids = merge_detail_ids(
            product_detail_ids=["300", "100"],
            mapped_detail_ids=["100", "200", "400"],
            existing_map_detail_ids=["100", "300"],
            missing_applicability_only=False,
            limit=2,
            offset=1,
        )

        self.assertEqual(detail_ids, ["200", "300"])
