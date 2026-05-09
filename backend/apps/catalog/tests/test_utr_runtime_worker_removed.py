from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase

from apps.catalog.tasks.utr_product_enrichment import (
    enrich_utr_product_task,
    enrich_visible_utr_applicability_task,
    enrich_visible_utr_catalog_products_task,
)


class UtrRuntimeWorkerRemovedTests(SimpleTestCase):
    def test_utr_applicability_defaults_are_disabled(self):
        self.assertFalse(settings.UTR_APPLICABILITY_ENABLED)
        self.assertFalse(settings.UTR_LAZY_CATALOG_APPLICABILITY_ENABLED)
        self.assertFalse(settings.UTR_LAZY_ENRICH_CHARACTERISTICS_ENABLED)
        self.assertFalse(settings.UTR_LAZY_ENRICH_APPLICABILITY_ENABLED)

    def test_utr_catalog_tasks_have_no_dedicated_queue_route(self):
        tasks = (
            enrich_utr_product_task,
            enrich_visible_utr_catalog_products_task,
            enrich_visible_utr_applicability_task,
        )
        for task in tasks:
            self.assertIn(getattr(task, "queue", None), (None, ""))

    def test_no_utr_catalog_beat_schedule_exists(self):
        tasks = [str(item.get("task", "")) for item in settings.CELERY_BEAT_SCHEDULE.values()]
        self.assertFalse(any("utr" in task.lower() for task in tasks))
