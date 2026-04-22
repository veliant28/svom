from __future__ import annotations

from dataclasses import dataclass
from typing import Any


THREAD_EVENT_TYPE = "support.event"


@dataclass(frozen=True)
class SupportGroups:
    @staticmethod
    def thread(thread_id: str) -> str:
        return f"support.thread.{thread_id}"

    @staticmethod
    def queue() -> str:
        return "support.queue"

    @staticmethod
    def wallboard() -> str:
        return "support.wallboard"

    @staticmethod
    def staff(user_id: int) -> str:
        return f"support.staff.{user_id}"

    @staticmethod
    def customer(user_id: int) -> str:
        return f"support.customer.{user_id}"


def make_event(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": THREAD_EVENT_TYPE,
        "event": {
            "type": event,
            "payload": payload,
        },
    }
