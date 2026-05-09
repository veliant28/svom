from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.selectors import get_header_navigation_payload


class HeaderNavigationAPIView(APIView):
    def get(self, request):
        locale = _resolve_locale(request)
        return Response(get_header_navigation_payload(locale=locale))


def _resolve_locale(request) -> str | None:
    locale = (request.query_params.get("locale") or "").strip()
    if locale:
        return locale
    language_code = getattr(request, "LANGUAGE_CODE", "")
    if language_code:
        return str(language_code)
    accept_language = str(request.headers.get("Accept-Language", "")).strip()
    if not accept_language:
        return None
    return accept_language.split(",", 1)[0]
