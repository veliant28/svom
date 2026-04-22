from __future__ import annotations

import json
import logging
from typing import Any

from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    get_channel_layer = None

from .events import make_event

logger = logging.getLogger(__name__)


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=str))


def publish_group_event(*, group: str, event: str, payload: dict[str, Any]) -> None:
    if get_channel_layer is None:
        logger.warning("support.realtime.channels_not_installed", extra={"group": group, "event": event})
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("support.realtime.channel_layer_missing", extra={"group": group, "event": event})
        return
    async_to_sync(channel_layer.group_send)(group, make_event(event, _json_safe(payload)))
