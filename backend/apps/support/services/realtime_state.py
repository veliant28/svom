from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlparse

import redis
from django.conf import settings

PRESENCE_ZSET_KEY = "support:presence:users"
PRESENCE_PAYLOAD_KEY = "support:presence:payload"
TYPING_KEY_TEMPLATE = "support:typing:{thread_id}:{side}:{user_id}"
TYPING_TTL_SECONDS = 5
PRESENCE_TTL_SECONDS = 30
WALLBOARD_SNAPSHOT_KEY = "support:wallboard:snapshot"
QUEUE_SNAPSHOT_KEY = "support:queue:snapshot"
COUNTERS_SNAPSHOT_KEY = "support:counters:{user_id}"


def get_support_redis() -> redis.Redis:
    redis_url = getattr(settings, "REDIS_CACHE_URL", None) or settings.CACHES["default"]["LOCATION"]
    parsed = urlparse(redis_url)
    db = 0
    if parsed.path and parsed.path.strip("/"):
        try:
            db = int(parsed.path.strip("/"))
        except ValueError:
            db = 0
    return redis.Redis(host=parsed.hostname, port=parsed.port or 6379, password=parsed.password, db=db, decode_responses=True)


def set_presence(*, user_id: int, role: str, ttl_seconds: int = PRESENCE_TTL_SECONDS) -> bool:
    now = int(time.time())
    expires_at = now + ttl_seconds
    client = get_support_redis()
    previous = client.zscore(PRESENCE_ZSET_KEY, str(user_id))
    client.zadd(PRESENCE_ZSET_KEY, {str(user_id): expires_at})
    client.hset(PRESENCE_PAYLOAD_KEY, str(user_id), json.dumps({"user_id": user_id, "role": role, "expires_at": expires_at}))
    return previous is None or previous < now


def take_expired_presence() -> list[dict[str, Any]]:
    now = int(time.time())
    client = get_support_redis()
    expired_ids = client.zrangebyscore(PRESENCE_ZSET_KEY, 0, now)
    if not expired_ids:
        return []
    payloads = client.hmget(PRESENCE_PAYLOAD_KEY, expired_ids)
    client.zrem(PRESENCE_ZSET_KEY, *expired_ids)
    client.hdel(PRESENCE_PAYLOAD_KEY, *expired_ids)
    rows: list[dict[str, Any]] = []
    for user_id, payload in zip(expired_ids, payloads, strict=False):
        if payload:
            row = json.loads(payload)
        else:
            row = {"user_id": int(user_id), "role": "unknown"}
        row["online"] = False
        rows.append(row)
    return rows


def is_user_online(user_id: int) -> bool:
    score = get_support_redis().zscore(PRESENCE_ZSET_KEY, str(user_id))
    if score is None:
        return False
    return score >= int(time.time())


def set_typing(*, thread_id: str, user_id: int, side: str, is_typing: bool) -> None:
    key = TYPING_KEY_TEMPLATE.format(thread_id=thread_id, side=side, user_id=user_id)
    client = get_support_redis()
    if is_typing:
        client.setex(key, TYPING_TTL_SECONDS, "1")
        return
    client.delete(key)


def list_typing_users(*, thread_id: str, side: str) -> list[int]:
    pattern = TYPING_KEY_TEMPLATE.format(thread_id=thread_id, side=side, user_id="*")
    client = get_support_redis()
    rows: list[int] = []
    for key in client.scan_iter(match=pattern):
        try:
            rows.append(int(str(key).rsplit(":", 1)[1]))
        except (TypeError, ValueError):
            continue
    return rows


def set_json_snapshot(key: str, payload: dict[str, Any], ttl_seconds: int = 60) -> None:
    get_support_redis().setex(key, ttl_seconds, json.dumps(payload, default=str))


def get_json_snapshot(key: str) -> dict[str, Any] | None:
    raw = get_support_redis().get(key)
    if not raw:
        return None
    return json.loads(raw)
