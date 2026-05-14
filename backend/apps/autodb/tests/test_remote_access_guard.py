from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.autodb.remote_access_guard import _build_guarded_connect


class AutoDbRemoteAccessGuardTests(SimpleTestCase):
    def test_guard_blocks_direct_connect(self):
        original = lambda: "ok"  # noqa: E731
        guarded = _build_guarded_connect(original)

        with patch("apps.autodb.remote_access_guard._stack_has_allowed_caller", return_value=False):
            with self.assertRaises(RuntimeError) as exc_ctx:
                guarded()

        self.assertIn("Direct remote DB connection is blocked", str(exc_ctx.exception))

    def test_guard_allows_gateway_connect(self):
        original = lambda: "ok"  # noqa: E731
        guarded = _build_guarded_connect(original)

        with patch("apps.autodb.remote_access_guard._stack_has_allowed_caller", return_value=True):
            self.assertEqual(guarded(), "ok")

