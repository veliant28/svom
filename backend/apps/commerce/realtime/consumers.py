from __future__ import annotations

import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .events import CommerceGroups


class CommerceUserConsumer(AsyncJsonWebsocketConsumer):
    group_name: str = ""

    @staticmethod
    def _json_safe(payload: dict) -> dict:
        return json.loads(json.dumps(payload, default=str))

    async def connect(self):
        user = self.scope.get("user")
        if not bool(user and user.is_authenticated):
            await self.close(code=4401)
            return

        self.group_name = CommerceGroups.customer(int(user.id))
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "commerce.connection.ready", "payload": {"user_id": str(user.id)}})

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Read-only channel for customer-facing order/return updates.
        return None

    async def commerce_event(self, event):
        await self.send_json(self._json_safe(event["event"]))

