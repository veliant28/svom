from __future__ import annotations

from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

from apps.commerce.services.vchasno_kasa.client import VchasnoKasaApiClient
from apps.commerce.services.vchasno_kasa.exceptions import VchasnoKasaApiError


class VchasnoKasaClientTests(TestCase):
    def test_http_error_uses_raw_message_from_non_json_payload(self):
        client = VchasnoKasaApiClient(token="token-123")
        http_error = HTTPError(
            url="https://kasa.vchasno.ua/api/v1/orders/list",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b"401: Unauthorized"),
        )

        with patch("apps.commerce.services.vchasno_kasa.client.urllib_request.urlopen", side_effect=http_error):
            with self.assertRaises(VchasnoKasaApiError) as ctx:
                client.list_orders({})

        self.assertEqual(str(ctx.exception), "401: Unauthorized")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.details, {"response": {"raw": "401: Unauthorized"}})

