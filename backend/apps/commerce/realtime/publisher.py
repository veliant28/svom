from __future__ import annotations

import json
import logging
from typing import Any

from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    get_channel_layer = None

from apps.commerce.models import Order, ReturnRequest
from apps.commerce.services import format_tracking_number

from .events import CommerceGroups, make_event

logger = logging.getLogger(__name__)


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=str))


def publish_group_event(*, group: str, event: str, payload: dict[str, Any]) -> None:
    if get_channel_layer is None:
        logger.warning("commerce.realtime.channels_not_installed", extra={"group": group, "event": event})
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("commerce.realtime.channel_layer_missing", extra={"group": group, "event": event})
        return
    async_to_sync(channel_layer.group_send)(group, make_event(event, _json_safe(payload)))


def publish_customer_order_updated(*, order: Order) -> None:
    if not order.user_id:
        return
    payload = {
        "order_id": str(order.id),
        "order_number": str(order.order_number or ""),
        "status": str(order.status or ""),
    }
    publish_group_event(
        group=CommerceGroups.customer(int(order.user_id)),
        event="commerce.order.updated",
        payload=payload,
    )


def publish_customer_return_updated(*, return_request: ReturnRequest) -> None:
    if not return_request.user_id:
        return
    payload = {
        "return_id": str(return_request.id),
        "return_number": str(return_request.return_number or ""),
        "order_number": str(getattr(return_request.order, "order_number", "") or ""),
        "status": str(return_request.status or ""),
        "tracking_number": format_tracking_number(return_request.customer_return_tracking_number),
        "admin_comment": str(return_request.admin_comment or ""),
    }
    publish_group_event(
        group=CommerceGroups.customer(int(return_request.user_id)),
        event="commerce.return.updated",
        payload=payload,
    )

