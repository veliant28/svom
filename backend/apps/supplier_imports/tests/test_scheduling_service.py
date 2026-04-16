from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services import ScheduledImportService


class ScheduledImportServiceTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="UTR", code="utr", is_active=True)
        self.source = ImportSource.objects.create(
            code="utr",
            name="UTR",
            supplier=self.supplier,
            parser_type=ImportSource.PARSER_UTR,
            input_path="",
            is_active=True,
            is_auto_import_enabled=True,
            schedule_cron="* * * * *",
            schedule_timezone="Europe/Kyiv",
        )

    def test_due_when_cron_matches_and_last_started_is_older(self):
        now = timezone.now().replace(second=0, microsecond=0)
        self.source.last_started_at = now - timedelta(minutes=1)
        self.source.save(update_fields=("last_started_at", "updated_at"))

        is_due = ScheduledImportService().is_source_due(source=self.source, now=now)
        self.assertTrue(is_due)

    def test_not_due_when_already_started_this_minute(self):
        now = timezone.now().replace(second=0, microsecond=0)
        self.source.last_started_at = now
        self.source.save(update_fields=("last_started_at", "updated_at"))

        is_due = ScheduledImportService().is_source_due(source=self.source, now=now)
        self.assertFalse(is_due)

    def test_next_run_is_calculated(self):
        next_run = ScheduledImportService().get_next_run(source=self.source, now=timezone.now())
        self.assertIsNotNone(next_run)
