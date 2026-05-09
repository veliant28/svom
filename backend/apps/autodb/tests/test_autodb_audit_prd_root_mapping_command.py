from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase


class AutoDbAuditPrdRootMappingCommandTests(SimpleTestCase):
    @patch("apps.autodb.management.commands.autodb_audit_prd_root_mapping.AutoDbRawCloneStorage")
    def test_command_exports_csv_and_summary(self, storage_cls):
        storage = Mock()
        storage.ensure_table.return_value = None
        storage.get_local_columns.return_value = {
            "id",
            "description",
            "normalizeddescription",
            "assemblygroupdescription",
            "usagedescription",
        }
        storage.fetch_local_rows.return_value = [
            {
                "id": 1,
                "description": "Свеча зажигания",
                "normalizeddescription": "Spark plug",
                "assemblygroupdescription": "Система зажигания / накаливания",
                "usagedescription": "",
            },
            {
                "id": 2,
                "description": "Комплектующие для узла",
                "normalizeddescription": "",
                "assemblygroupdescription": "Комплектующие",
                "usagedescription": "",
            },
        ]
        storage_cls.return_value = storage

        out = StringIO()
        with TemporaryDirectory() as tmp_dir:
            export_csv = str(Path(tmp_dir) / "prd_root_mapping.csv")
            call_command(
                "autodb_audit_prd_root_mapping",
                "--limit",
                "100",
                "--export-csv",
                export_csv,
                stdout=out,
            )

            content = Path(export_csv).read_text(encoding="utf-8")
            self.assertIn("prd_id", content)
            self.assertIn("Система зажигания / накаливания", content)

        text = out.getvalue()
        self.assertIn("total_prd_checked: 2", text)
        self.assertIn("mapped: 1", text)
        self.assertIn("needs_review: 1", text)
        self.assertIn("UTR calls=0", text)
