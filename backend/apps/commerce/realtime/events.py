from __future__ import annotations

from dataclasses import dataclass
from typing import Any


COMMERCE_EVENT_TYPE = "commerce.event"


@dataclass(frozen=True)
class CommerceGroups:
    @staticmethod
    def customer(user_id: int) -> str:
        return f"commerce.customer.{user_id}"


def make_event(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": COMMERCE_EVENT_TYPE,
        "event": {
            "type": event,
            "payload": payload,
        },
    }

