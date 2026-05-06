from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.autocatalog.application.utr_import_command import CommandOutput, run_utr_import_command


@override_settings(UTR_CATALOG_ENRICHMENT_ENABLED=False)
class UtrImportCommandKillSwitchTests(SimpleTestCase):
    @patch("apps.autocatalog.application.utr_import_command.runner.modes.run_autocatalog_import_flow")
    def test_command_returns_warning_and_does_not_run_flow(self, run_flow_mock):
        lines: list[str] = []
        output = CommandOutput(
            write=lines.append,
            success=lambda message: message,
            warning=lambda message: message,
        )

        run_utr_import_command(raw_options={}, output=output)

        self.assertIn("UTR catalog enrichment is disabled", lines)
        run_flow_mock.assert_not_called()
