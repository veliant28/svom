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
            recent_points_json=[
                {
                    "timestamp": (now - timedelta(minutes=1)).replace(second=0, microsecond=0).isoformat(),
                    "query_count": 100,
                    "cumulative_used": 100,
                    "run_id": "tecdoc-batch",
                    "consumer": "celery_batch",
                    "status": "ok",
                    "error": "",
                }
            ],
        )
        tracker = AutoDbRemoteQuotaTracker()

        tracker.record_success(quota, query_count=1, run_id="tecdoc-batch")

        quota.refresh_from_db()
        self.assertEqual(quota.estimated_limit_per_hour, 1000)
        self.assertEqual(quota.estimated_queries_used, 101)

    def test_local_limit_reach_does_not_auto_pause_without_remote_quota_error(self):
        now = timezone.now()
        quota = AutoDbRemoteQuotaState.objects.create(
            remote_key="autodb_pro_mysql",
            estimated_limit_per_hour=1000,
            estimated_queries_used=999,
            window_started_at=now,
            expected_reset_at=now + timedelta(minutes=30),
            recent_points_json=[
                {
                    "timestamp": (now - timedelta(minutes=1)).replace(second=0, microsecond=0).isoformat(),
                    "query_count": 999,
                    "cumulative_used": 999,
                    "run_id": "tecdoc-batch",
                    "consumer": "celery_batch",
                    "status": "ok",
                    "error": "",
                }
            ],
        )
        tracker = AutoDbRemoteQuotaTracker()

        tracker.record_success(quota, query_count=1, run_id="tecdoc-batch")

        quota.refresh_from_db()
        payload = tracker.serialize(quota)
        self.assertEqual(quota.estimated_queries_used, 1000)
        self.assertIsNone(quota.cooldown_until)
        self.assertEqual(payload.get("status"), "warning")

    def test_serialize_does_not_hard_reset_used_on_expected_reset_boundary(self):
        now = timezone.now()
        old_expected_reset = now - timedelta(seconds=30)
        quota = AutoDbRemoteQuotaState.objects.create(
            remote_key="autodb_pro_mysql",
            estimated_limit_per_hour=3332,
            estimated_queries_used=2143,
            window_started_at=now - timedelta(hours=1),
            expected_reset_at=old_expected_reset,
            recent_points_json=[
                {
                    "timestamp": (now - timedelta(minutes=2)).replace(second=0, microsecond=0).isoformat(),
                    "query_count": 2143,
                    "cumulative_used": 2143,
                    "run_id": "tecdoc-batch",
                    "consumer": "celery_batch",
                    "status": "ok",
                    "error": "",
                }
            ],
        )
        tracker = AutoDbRemoteQuotaTracker()

        payload = tracker.serialize(quota)
        quota.refresh_from_db()

        self.assertEqual(quota.estimated_queries_used, 2143)
        self.assertEqual(int(payload.get("estimated_queries_used") or 0), 2143)

    def test_cooldown_expiry_resets_counter_to_zero(self):
        now = timezone.now()
        quota = AutoDbRemoteQuotaState.objects.create(
            remote_key="autodb_pro_mysql",
            estimated_limit_per_hour=3332,
            estimated_queries_used=2825,
            cooldown_until=now - timedelta(seconds=5),
            last_quota_error_at=now - timedelta(minutes=1),
            window_started_at=now - timedelta(minutes=30),
            expected_reset_at=now + timedelta(minutes=30),
            recent_points_json=[
                {
                    "timestamp": (now - timedelta(minutes=1)).replace(second=0, microsecond=0).isoformat(),
                    "query_count": 2825,
                    "cumulative_used": 2825,
                    "run_id": "tecdoc-batch",
                    "consumer": "celery_batch",
                    "status": "ok",
                    "error": "",
                }
            ],
            last_error="ERROR 1226 (42000): max_questions",
        )
        tracker = AutoDbRemoteQuotaTracker()

        payload = tracker.serialize(quota)
        quota.refresh_from_db()

        self.assertEqual(quota.estimated_queries_used, 0)
        self.assertEqual(int(payload.get("estimated_queries_used") or 0), 0)
        self.assertIsNone(quota.cooldown_until)
        self.assertEqual(quota.recent_points_json, [])

    def test_active_cooldown_keeps_used_frozen(self):
        now = timezone.now()
        quota = AutoDbRemoteQuotaState.objects.create(
            remote_key="autodb_pro_mysql",
            estimated_limit_per_hour=3332,
            estimated_queries_used=2825,
            cooldown_until=now + timedelta(minutes=20),
            last_quota_error_at=now - timedelta(minutes=1),
            window_started_at=now - timedelta(minutes=59),
            expected_reset_at=now + timedelta(minutes=1),
            recent_points_json=[
                {
                    "timestamp": (now - timedelta(minutes=59)).replace(second=0, microsecond=0).isoformat(),
                    "query_count": 2825,
                    "cumulative_used": 2825,
                    "run_id": "tecdoc-batch",
                    "consumer": "celery_batch",
                    "status": "ok",
                    "error": "",
                }
            ],
        )
        tracker = AutoDbRemoteQuotaTracker()

        payload = tracker.serialize(quota)
        quota.refresh_from_db()

        self.assertEqual(quota.estimated_queries_used, 2825)
        self.assertEqual(int(payload.get("estimated_queries_used") or 0), 2825)
        self.assertEqual(payload.get("status"), "quota_paused")
