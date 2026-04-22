from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.support.models import SupportThread
from apps.support.selectors import build_queue_snapshot, build_user_counters, build_wallboard_snapshot, serialize_user
from apps.support.services import (
    build_typing_payload,
    can_access_thread_id,
    ensure_support_staff,
    mark_support_thread_read,
    resolve_support_role,
    set_support_typing,
    touch_support_presence,
)
from .events import SupportGroups


class BaseSupportConsumer(AsyncJsonWebsocketConsumer):
    group_names: tuple[str, ...] = ()

    @staticmethod
    def _json_safe(payload: dict) -> dict:
        return json.loads(json.dumps(payload, default=str))

    async def connect(self):
        user = self.scope.get("user")
        if not bool(user and user.is_authenticated):
            await self.close(code=4401)
            return

        allowed = await self.is_allowed()
        if not allowed:
            await self.close(code=4403)
            return

        self.group_names = tuple(await self.resolve_groups())
        for group_name in self.group_names:
            await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()
        await self.handle_presence_heartbeat()
        await self.after_connect()

    async def disconnect(self, close_code):
        for group_name in self.group_names:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def is_allowed(self) -> bool:
        return True

    async def resolve_groups(self) -> list[str]:
        return []

    async def after_connect(self) -> None:
        return None

    async def receive_json(self, content, **kwargs):
        event_type = str(content.get("type") or "").strip()
        if event_type == "support.presence.heartbeat":
            await self.handle_presence_heartbeat()
            return
        await self.handle_client_event(event_type=event_type, payload=content)

    async def handle_client_event(self, *, event_type: str, payload: dict) -> None:
        return None

    async def handle_presence_heartbeat(self) -> None:
        await self.touch_presence()

    async def support_event(self, event):
        await self.send_json(self._json_safe(event["event"]))

    @database_sync_to_async
    def touch_presence(self) -> None:
        touch_support_presence(user=self.scope["user"])


class SupportUserConsumer(BaseSupportConsumer):
    async def resolve_groups(self) -> list[str]:
        user = self.scope["user"]
        role = await self.get_user_role()
        if role == "staff":
            return [SupportGroups.staff(user.id)]
        return [SupportGroups.customer(user.id)]

    async def after_connect(self) -> None:
        payload = await self.get_initial_payload()
        await self.send_json(self._json_safe({"type": "support.connection.ready", "payload": payload}))

    @database_sync_to_async
    def get_user_role(self) -> str:
        return resolve_support_role(self.scope["user"])

    @database_sync_to_async
    def get_initial_payload(self) -> dict:
        user = self.scope["user"]
        return {
            "counters": build_user_counters(user=user),
        }


class SupportQueueConsumer(BaseSupportConsumer):
    @database_sync_to_async
    def is_allowed(self) -> bool:
        try:
            ensure_support_staff(self.scope["user"])
            return True
        except Exception:
            return False

    async def resolve_groups(self) -> list[str]:
        return [SupportGroups.queue()]

    async def after_connect(self) -> None:
        payload = await self.get_queue_payload()
        await self.send_json(self._json_safe({"type": "support.queue.updated", "payload": payload}))

    @database_sync_to_async
    def get_queue_payload(self) -> dict:
        return build_queue_snapshot()


class SupportWallboardConsumer(BaseSupportConsumer):
    @database_sync_to_async
    def is_allowed(self) -> bool:
        try:
            ensure_support_staff(self.scope["user"])
            return True
        except Exception:
            return False

    async def resolve_groups(self) -> list[str]:
        return [SupportGroups.wallboard()]

    async def after_connect(self) -> None:
        payload = await self.get_wallboard_payload()
        await self.send_json(self._json_safe({"type": "support.wallboard.updated", "payload": payload}))

    @database_sync_to_async
    def get_wallboard_payload(self) -> dict:
        return build_wallboard_snapshot()


class SupportThreadConsumer(BaseSupportConsumer):
    thread_id: str = ""

    async def connect(self):
        self.thread_id = str(self.scope["url_route"]["kwargs"]["thread_id"])
        await super().connect()

    @database_sync_to_async
    def is_allowed(self) -> bool:
        return can_access_thread_id(user=self.scope["user"], thread_id=self.thread_id)

    async def resolve_groups(self) -> list[str]:
        return [SupportGroups.thread(self.thread_id)]

    async def after_connect(self) -> None:
        payload = await self.get_thread_payload()
        await self.send_json(self._json_safe({"type": "support.thread.bootstrap", "payload": payload}))

    async def handle_client_event(self, *, event_type: str, payload: dict) -> None:
        if event_type == "support.typing.start":
            typing_payload = await self.set_typing(True)
            await self.send_json(self._json_safe({"type": "support.typing.updated", "payload": typing_payload}))
            return
        if event_type == "support.typing.stop":
            typing_payload = await self.set_typing(False)
            await self.send_json(self._json_safe({"type": "support.typing.updated", "payload": typing_payload}))
            return
        if event_type == "support.thread.read":
            read_payload = await self.mark_read()
            await self.send_json(self._json_safe({"type": "support.thread.read", "payload": read_payload}))

    @database_sync_to_async
    def get_thread_payload(self) -> dict:
        thread = SupportThread.objects.select_related("customer", "assigned_staff").filter(id=self.thread_id).first()
        return {
            "thread_id": self.thread_id,
            "typing": build_typing_payload(thread_id=self.thread_id),
            "assigned_staff": serialize_user(thread.assigned_staff) if thread else None,
        }

    @database_sync_to_async
    def set_typing(self, is_typing: bool) -> dict:
        thread = SupportThread.objects.get(id=self.thread_id)
        return set_support_typing(thread=thread, user=self.scope["user"], is_typing=is_typing)

    @database_sync_to_async
    def mark_read(self) -> dict:
        thread = SupportThread.objects.get(id=self.thread_id)
        state = mark_support_thread_read(thread=thread, user=self.scope["user"])
        return {
            "thread_id": self.thread_id,
            "last_read_message_id": state.last_read_message_id,
            "last_read_at": state.last_read_at,
        }
