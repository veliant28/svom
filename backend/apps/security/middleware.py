from __future__ import annotations

from django.http import JsonResponse

from apps.security.services.events import record_security_event_from_request
from apps.security.services.enforcement import (
    find_matching_security_block,
    log_rejected_request,
    serialize_blocked_payload,
)


class SecurityBlockEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            match = find_matching_security_block(request)
        except Exception:
            match = None

        if match is not None:
            try:
                log_rejected_request(match, request)
            except Exception:
                pass
            payload = serialize_blocked_payload(match)
            response = JsonResponse(payload, status=403)
            response["X-Security-Blocked"] = "1"
            return response

        return self.get_response(request)


class SecurityEventCaptureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            record_security_event_from_request(request=request, response=response)
        except Exception:
            # Security telemetry must never break the primary request.
            return response
        return response
