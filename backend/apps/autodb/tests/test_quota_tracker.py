from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.autodb.models import AutoDbRemoteQuotaState
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker


@override_settings(AUTODB_PRO_REMOTE_LIMIT_PER_HOUR=10000)
class AutoDbRemoteQuotaTrackerTests(TestCase):
    databases = {"default"}

    def test_quota_error_infers_lower_limit_from_mysql_message(self):
        quota = AutoDbRemoteQuotaState.objects.create(
            remote_key="autodb_pro_mysql",
            estimated_limit_per_hour=10000,
            estimated_queries_used=373,
        )
        tracker = AutoDbRemoteQuotaTracker()

        tracker.record_quota_error(
            quota,
            error="ERROR 1226 (42000): User 'demo' has exceeded the 'max_questions' resource (current value: 1000)",
            cooldown_minutes=60,
            run_id="tecdoc-batch",
        )

        quota.refresh_from_db()
        self.assertEqual(quota.estimated_limit_per_hour, 1000)
        self.assertEqual(quota.estimated_queries_used, 1000)
        self.assertIsNotNone(quota.cooldown_until)

    def test_ensure_window_keeps_existing_lower_limit(self):
        now = timezone.now()
        quota = AutoDbRemoteQuotaState.objects.create(
            remote_key="autodb_pro_mysql",
            estimated_limit_per_hour=1000,
            estimated_queries_used=100,
            window_started_at=now,
            expected_reset_at=now + timedelta(minutes=30),
        )
        tracker = AutoDbRemoteQuotaTracker()

        tracker.record_success(quota, query_count=1, run_id="tecdoc-batch")

        quota.refresh_from_db()
        self.assertEqual(quota.estimated_limit_per_hour, 1000)
        self.assertEqual(quota.estimated_queries_used, 101)
