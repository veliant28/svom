from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from rest_framework.authtoken.models import Token


@database_sync_to_async
def get_user_for_token(token_key: str):
    if not token_key:
        return AnonymousUser()

    close_old_connections()
    token = Token.objects.select_related("user").filter(key=token_key).first()
    if token is None or not token.user.is_active:
        return AnonymousUser()
    return token.user


class TokenQueryAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query = parse_qs(query_string)
        token_key = (query.get("token") or [""])[0].strip()
        scope["user"] = await get_user_for_token(token_key)
        return await self.app(scope, receive, send)
