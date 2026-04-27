from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services import ScheduledImportService


class ScheduledImportServiceTests(TestCase):
    def setUp(self):
        cache.clear()
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

    def test_due_when_previous_scheduled_slot_was_missed(self):
        local_now = datetime(2026, 4, 27, 7, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.source.schedule_cron = "0 1 * * *"
        self.source.last_started_at = datetime(2026, 4, 26, 22, 27, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.source.save(update_fields=("schedule_cron", "last_started_at", "updated_at"))

        is_due = ScheduledImportService().is_source_due(source=self.source, now=local_now)

        self.assertTrue(is_due)

    def test_not_due_when_missed_slot_was_already_started(self):
        local_now = datetime(2026, 4, 27, 7, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.source.schedule_cron = "0 1 * * *"
        self.source.last_started_at = datetime(2026, 4, 27, 1, 1, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.source.save(update_fields=("schedule_cron", "last_started_at", "updated_at"))

        is_due = ScheduledImportService().is_source_due(source=self.source, now=local_now)

        self.assertFalse(is_due)

    @patch("apps.supplier_imports.tasks.run_scheduled_supplier_pipeline.run_scheduled_supplier_pipeline_task.delay")
    def test_missed_slot_is_dispatched_once(self, delay_mock):
        delay_mock.return_value.id = "task-1"
        local_now = datetime(2026, 4, 27, 7, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.source.schedule_cron = "0 1 * * *"
        self.source.last_started_at = datetime(2026, 4, 26, 22, 27, tzinfo=ZoneInfo("Europe/Kyiv"))
        self.source.save(update_fields=("schedule_cron", "last_started_at", "updated_at"))
        service = ScheduledImportService()

        first = service.dispatch_due_sources(now=local_now)
        second = service.dispatch_due_sources(now=local_now + timedelta(minutes=1))

        self.assertEqual(first[0].status, "scheduled")
        self.assertEqual(first[0].reason, "due")
        self.assertEqual(second[0].status, "skipped")
        self.assertEqual(second[0].reason, "dispatch_locked")
        delay_mock.assert_called_once_with(source_code="utr")
