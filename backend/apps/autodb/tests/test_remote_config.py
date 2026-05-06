from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator


class AutoDbRemoteConfigValidatorTests(SimpleTestCase):
    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="db.auto-db.pro",
        AUTODB_PRO_REMOTE_PORT=3306,
        AUTODB_PRO_REMOTE_DATABASE="db",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    def test_sanitized_config_hides_password(self):
        snapshot = AutoDbRemoteConfigValidator.snapshot()

        sanitized = snapshot.sanitized()
        self.assertTrue(sanitized["password_set"])
        self.assertNotIn("password", sanitized)

    @override_settings(
        AUTODB_PRO_REMOTE_ENABLED=True,
        AUTODB_PRO_REMOTE_HOST="",
        AUTODB_PRO_REMOTE_DATABASE="db",
        AUTODB_PRO_REMOTE_USER="tester",
        AUTODB_PRO_REMOTE_PASSWORD="secret",
    )
    def test_ensure_remote_ready_raises_for_invalid_config(self):
        with self.assertRaises(AutoDbRemoteConfigError):
            AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)

    @override_settings(AUTODB_PRO_REMOTE_ENABLED=False)
    def test_allow_remote_false_does_not_raise(self):
        AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=False)
