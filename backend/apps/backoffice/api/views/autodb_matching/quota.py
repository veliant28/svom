from __future__ import annotations

from rest_framework.response import Response

from apps.autodb.models import AutoDbRemoteQuotaState
from apps.autodb.services.matching.constants import REMOTE_QUOTA_KEY
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker

from .._base import BackofficeAPIView


class BackofficeAutoDbMatchingRemoteQuotaAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        quota = AutoDbRemoteQuotaState.objects.filter(remote_key=REMOTE_QUOTA_KEY).first()
        payload = AutoDbRemoteQuotaTracker().serialize(quota)
        return Response(payload)
