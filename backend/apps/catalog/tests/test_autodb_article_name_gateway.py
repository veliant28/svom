from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.catalog.services.autodb_content import resolve_autodb_article_name


@override_settings(
    AUTODB_LIVE_CONTENT_ENABLED=True,
    AUTODB_CONTENT_CACHE_TTL_SECONDS=60,
)
class AutoDbArticleNameGatewayTests(SimpleTestCase):
    @patch("apps.catalog.services.autodb_content.cache")
    @patch("apps.catalog.services.autodb_content.AutoDbProRemoteClient")
    def test_resolve_name_uses_remote_gateway(self, remote_client_cls, cache_mock):
        cache_mock.get.return_value = None
        client = remote_client_cls.from_settings.return_value
        client.select.side_effect = [
            [{"id": 101}],
            [{"info_type": "article_name", "info_text": "Bosch S5 Battery"}],
        ]

        resolved = resolve_autodb_article_name(
            normalized_article="0092S50070",
            normalized_brand="BOSCH",
            prefer_live=True,
        )

        self.assertEqual(resolved, "Bosch S5 Battery")
        self.assertEqual(client.select.call_count, 2)
        first_query, first_params = client.select.call_args_list[0][0][:2]
        second_query, second_params = client.select.call_args_list[1][0][:2]
        self.assertIn("FROM suppliers", first_query)
        self.assertEqual(first_params, ("BOSCH", "BOSCH"))
        self.assertIn("FROM article_inf", second_query)
        self.assertIn("0092S50070", second_params)

    @patch("apps.catalog.services.autodb_content.cache")
    @patch("apps.catalog.services.autodb_content._load_article_name_from_live")
    @patch("apps.catalog.services.autodb_content.AutoDbProRemoteClient")
    def test_resolve_name_does_not_fallback_to_direct_mysql_path(self, remote_client_cls, live_loader_mock, cache_mock):
        cache_mock.get.return_value = None
        remote_client_cls.from_settings.side_effect = RuntimeError("gateway unavailable")

        resolved = resolve_autodb_article_name(
            normalized_article="0092S50070",
            normalized_brand="BOSCH",
            prefer_live=True,
        )

        self.assertEqual(resolved, "")
        live_loader_mock.assert_not_called()
