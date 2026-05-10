from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.security.models import SecurityActor, SecurityBlock, SecurityEvent
from apps.security.services.audit import request_ip, request_user_agent

SECURITY_BLOCK_MODE_SOFT = "soft"
SECURITY_BLOCK_MODE_HARD = "hard"
SECURITY_BLOCK_MODES = {SECURITY_BLOCK_MODE_SOFT, SECURITY_BLOCK_MODE_HARD}

SECURITY_BLOCK_ERROR_CODE = "security_blocked"

_TOKEN_CACHE_TTL_SECONDS = 300
_DECISION_CACHE_TTL_SECONDS = 20
_LOG_THROTTLE_SECONDS = 60

_CACHE_KEY_REVISION = "security:block-enforcement:revision"
_CACHE_KEY_DECISION_PREFIX = "security:block-enforcement:decision:v2"
_CACHE_KEY_TOKEN_PREFIX = "security:block-enforcement:token-user:v1"
_CACHE_KEY_LOG_PREFIX = "security:block-enforcement:reject-log:v1"

_HARD_BLOCK_EXEMPT_PREFIXES = (
    "/api/core/health/",
    "/api/core/security-blocked-info/",
)
_SOFT_BLOCK_PREFIXES = (
    "/api/users/auth/",
    "/api/users/garage-vehicles/",
    "/api/commerce/cart/",
    "/api/commerce/checkout/",
    "/api/commerce/orders/",
    "/api/commerce/account/",
    "/api/commerce/loyalty/",
    "/api/commerce/support/",
)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_FINGERPRINT_HEADER_CANDIDATES = (
    "HTTP_X_DEVICE_FINGERPRINT",
    "HTTP_X_FINGERPRINT",
    "HTTP_X_CLIENT_FINGERPRINT",
    "HTTP_X_SESSION_FINGERPRINT",
)
_SESSION_COOKIE_CANDIDATE = "sessionid"


@dataclass
class SecurityBlockMatch:
    block_id: str
    actor_id: str | None
    block_type: str
    reason: str
    expires_at: str | None
    actor_threat_level: str
    actor_source_ip: str | None
    actor_source_kind: str
    actor_login_snapshot: str
    actor_email_snapshot: str
    mode: str
    user_id: int | None
    source_ip: str
    session_key: str
    fingerprint: str
    user_agent: str


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized(value: str | None) -> str:
    return str(value or "").strip()


def _normalized_lower(value: str | None) -> str:
    return _normalized(value).lower()


def _current_revision() -> int:
    cached = cache.get(_CACHE_KEY_REVISION)
    if isinstance(cached, int):
        return max(1, cached)
    cache.set(_CACHE_KEY_REVISION, 1, timeout=None)
    return 1


def touch_block_enforcement_revision() -> None:
    try:
        cache.incr(_CACHE_KEY_REVISION)
    except Exception:
        cache.set(_CACHE_KEY_REVISION, _current_revision() + 1, timeout=None)


def _auth_token_from_request(request) -> str:
    header = _normalized(request.META.get("HTTP_AUTHORIZATION"))
    if not header:
        return ""
    match = re.match(r"^Token\s+(.+)$", header, flags=re.IGNORECASE)
    return _normalized(match.group(1) if match else "")


def _token_user_id(token_key: str) -> int | None:
    if not token_key:
        return None
    cache_key = f"{_CACHE_KEY_TOKEN_PREFIX}:{_sha(token_key)}"
    cached = cache.get(cache_key)
    if cached is not None:
        try:
            return int(cached)
        except (TypeError, ValueError):
            return None
    user_id = (
        Token.objects.filter(key=token_key)
        .values_list("user_id", flat=True)
        .first()
    )
    if user_id is None:
        cache.set(cache_key, "", timeout=_TOKEN_CACHE_TTL_SECONDS)
        return None
    cache.set(cache_key, int(user_id), timeout=_TOKEN_CACHE_TTL_SECONDS)
    return int(user_id)


def _request_user_id(request) -> int | None:
    if getattr(request, "user", None) is not None and getattr(request.user, "is_authenticated", False):
        return int(request.user.id)
    return _token_user_id(_auth_token_from_request(request))


def _request_fingerprint(request) -> str:
    for header in _FINGERPRINT_HEADER_CANDIDATES:
        value = _normalized(request.META.get(header))
        if value:
            return value[:255]
    return ""


def _request_session_key(request) -> str:
    session_obj = getattr(request, "session", None)
    session_key = _normalized(getattr(session_obj, "session_key", ""))
    if session_key:
        return session_key[:255]
    return _normalized(request.COOKIES.get(_SESSION_COOKIE_CANDIDATE))[:255]


def _request_identity_payload(request) -> dict[str, object]:
    user_id = _request_user_id(request)
    source_ip = request_ip(request)
    source_ip = source_ip if source_ip else ""
    fingerprint = _request_fingerprint(request)
    session_key = _request_session_key(request)
    user_agent = _normalized(request_user_agent(request))[:1024]
    user_agent_lc = user_agent.lower()
    return {
        "user_id": user_id,
        "source_ip": source_ip,
        "fingerprint": fingerprint,
        "session_key": session_key,
        "user_agent": user_agent,
        "user_agent_lc": user_agent_lc,
        "path": str(getattr(request, "path", "") or ""),
        "method": str(getattr(request, "method", "GET") or "GET").upper(),
    }


def _whitelist_candidate_identifiers(payload: dict[str, object]) -> set[str]:
    identifiers: set[str] = set()
    source_ip = str(payload["source_ip"] or "")
    fingerprint = str(payload["fingerprint"] or "")
    session_key = str(payload["session_key"] or "")
    user_agent = str(payload["user_agent"] or "")
    user_agent_lc = str(payload["user_agent_lc"] or "")
    user_id = payload["user_id"]
    if source_ip:
        identifiers.add(source_ip)
    if fingerprint:
        identifiers.add(fingerprint)
    if session_key:
        identifiers.add(session_key)
    if user_agent:
        identifiers.add(user_agent)
    if user_agent_lc:
        identifiers.add(user_agent_lc)
    if isinstance(user_id, int):
        identifiers.add(str(user_id))
    return identifiers


def _is_whitelisted(payload: dict[str, object]) -> bool:
    user_id = payload["user_id"] if isinstance(payload["user_id"], int) else None
    identifiers = sorted(_whitelist_candidate_identifiers(payload))
    cache_material = "|".join(identifiers) + f"|uid:{user_id or 0}"
    cache_key = f"{_CACHE_KEY_DECISION_PREFIX}:whitelist:{_current_revision()}:{_sha(cache_material)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return bool(cached)

    queryset = SecurityActor.objects.filter(status=SecurityActor.STATUS_WHITELISTED)
    filter_q = Q()
    if identifiers:
        filter_q |= Q(source_identifier__in=identifiers)
    if user_id is not None:
        filter_q |= Q(user_id=user_id)

    result = bool(filter_q) and queryset.filter(filter_q).exists()
    cache.set(cache_key, 1 if result else 0, timeout=_DECISION_CACHE_TTL_SECONDS)
    return result


def _matches_subnet(subnet_raw: str, source_ip: str) -> bool:
    if not subnet_raw or not source_ip:
        return False
    try:
        network = ipaddress.ip_network(subnet_raw, strict=False)
        address = ipaddress.ip_address(source_ip)
    except ValueError:
        return False
    return address in network


def resolve_block_mode(block: SecurityBlock) -> str:
    metadata = block.metadata if isinstance(block.metadata, dict) else {}
    mode = _normalized_lower(metadata.get("block_mode"))
    if mode in SECURITY_BLOCK_MODES:
        return mode
    return SECURITY_BLOCK_MODE_HARD


def _matches_block(block: SecurityBlock, payload: dict[str, object]) -> bool:
    source_ip = str(payload["source_ip"] or "")
    user_id = payload["user_id"] if isinstance(payload["user_id"], int) else None
    session_key = str(payload["session_key"] or "")
    fingerprint = str(payload["fingerprint"] or "")
    user_agent = str(payload["user_agent"] or "")
    user_agent_lc = str(payload["user_agent_lc"] or "")

    value = _normalized(block.value)
    value_lc = value.lower()

    if block.block_type == SecurityBlock.TYPE_IP:
        return bool(source_ip and value == source_ip)
    if block.block_type == SecurityBlock.TYPE_ACCOUNT:
        if user_id is None:
            return False
        actor_user_id = getattr(block.actor, "user_id", None)
        return value in {str(user_id), ""} or (actor_user_id is not None and int(actor_user_id) == int(user_id))
    if block.block_type == SecurityBlock.TYPE_FINGERPRINT:
        return bool(value and value in {fingerprint, session_key})
    if block.block_type == SecurityBlock.TYPE_USER_AGENT:
        return bool(value and value_lc in {user_agent.lower(), user_agent_lc})
    if block.block_type == SecurityBlock.TYPE_SUBNET:
        return _matches_subnet(value, source_ip)

    actor_identifier = _normalized(getattr(block.actor, "source_identifier", ""))
    return bool(
        actor_identifier
        and actor_identifier in {source_ip, fingerprint, session_key, user_agent, user_agent_lc, str(user_id) if user_id is not None else ""}
    )


def _is_api_path(path: str) -> bool:
    return path.startswith("/api/")


def _is_hard_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _HARD_BLOCK_EXEMPT_PREFIXES)


def _is_soft_target(path: str, method: str) -> bool:
    if any(path.startswith(prefix) for prefix in _SOFT_BLOCK_PREFIXES):
        return True
    return _is_api_path(path) and method not in _SAFE_METHODS


def _block_applies_for_request(mode: str, path: str, method: str) -> bool:
    if not _is_api_path(path):
        return False
    if mode == SECURITY_BLOCK_MODE_HARD:
        return not _is_hard_exempt(path)
    return _is_soft_target(path, method)


def _active_block_queryset(payload: dict[str, object]):
    now = timezone.now()
    source_ip = str(payload["source_ip"] or "")
    user_id = payload["user_id"] if isinstance(payload["user_id"], int) else None
    fingerprint = str(payload["fingerprint"] or "")
    session_key = str(payload["session_key"] or "")
    user_agent = str(payload["user_agent"] or "")
    user_agent_lc = str(payload["user_agent_lc"] or "")

    identifiers = {source_ip, fingerprint, session_key, user_agent, user_agent_lc}
    identifiers = {value for value in identifiers if value}
    account_values = {str(user_id)} if user_id is not None else set()
    fingerprint_values = {value for value in {fingerprint, session_key} if value}
    user_agent_values = {value for value in {user_agent, user_agent_lc} if value}

    active_q = Q(status=SecurityBlock.STATUS_ACTIVE) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    match_q = Q(block_type=SecurityBlock.TYPE_SUBNET)
    if source_ip:
        match_q |= (Q(block_type=SecurityBlock.TYPE_IP) & Q(value=source_ip))
    if account_values:
        match_q |= (Q(block_type=SecurityBlock.TYPE_ACCOUNT) & Q(value__in=account_values))
    if fingerprint_values:
        match_q |= (Q(block_type=SecurityBlock.TYPE_FINGERPRINT) & Q(value__in=fingerprint_values))
    if user_agent_values:
        match_q |= (Q(block_type=SecurityBlock.TYPE_USER_AGENT) & Q(value__in=user_agent_values))
    if identifiers:
        match_q |= Q(actor__source_identifier__in=identifiers)
    if user_id is not None:
        match_q |= Q(actor__user_id=user_id)

    return SecurityBlock.objects.select_related("actor").filter(active_q).filter(match_q).order_by("-blocked_at")


def find_matching_security_block(request) -> SecurityBlockMatch | None:
    payload = _request_identity_payload(request)
    path = str(payload["path"])
    method = str(payload["method"])
    if not _is_api_path(path):
        return None
    if _is_hard_exempt(path):
        return None
    if _is_whitelisted(payload):
        return None

    revision = _current_revision()
    identity_material = "|".join(
        [
            str(payload["user_id"] or ""),
            str(payload["source_ip"] or ""),
            str(payload["fingerprint"] or ""),
            str(payload["session_key"] or ""),
            str(payload["user_agent_lc"] or ""),
            path,
            method,
        ]
    )
    cache_key = f"{_CACHE_KEY_DECISION_PREFIX}:match:{revision}:{_sha(identity_material)}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        block_id = _normalized(cached.get("block_id"))
        mode = _normalized_lower(cached.get("mode"))
        if block_id and mode in SECURITY_BLOCK_MODES and _block_applies_for_request(mode, path, method):
            return SecurityBlockMatch(
                block_id=block_id,
                actor_id=_normalized(cached.get("actor_id")) or None,
                block_type=_normalized(cached.get("block_type")),
                reason=_normalized(cached.get("reason")),
                expires_at=_normalized(cached.get("expires_at")) or None,
                actor_threat_level=_normalized(cached.get("actor_threat_level")),
                actor_source_ip=_normalized(cached.get("actor_source_ip")) or None,
                actor_source_kind=_normalized(cached.get("actor_source_kind")),
                actor_login_snapshot=_normalized(cached.get("actor_login_snapshot")),
                actor_email_snapshot=_normalized(cached.get("actor_email_snapshot")),
                mode=mode,
                user_id=payload["user_id"] if isinstance(payload["user_id"], int) else None,
                source_ip=str(payload["source_ip"] or ""),
                session_key=str(payload["session_key"] or ""),
                fingerprint=str(payload["fingerprint"] or ""),
                user_agent=str(payload["user_agent"] or ""),
            )
        if cached.get("none") == 1:
            return None

    best_match: SecurityBlockMatch | None = None
    for block in _active_block_queryset(payload):
        if not _matches_block(block, payload):
            continue
        mode = resolve_block_mode(block)
        if not _block_applies_for_request(mode, path, method):
            continue
        match = SecurityBlockMatch(
            block_id=str(block.id),
            actor_id=str(block.actor_id) if block.actor_id else None,
            block_type=block.block_type,
            reason=_normalized(block.reason),
            expires_at=block.expires_at.isoformat() if block.expires_at else None,
            actor_threat_level=_normalized(getattr(block.actor, "threat_level", "")),
            actor_source_ip=getattr(block.actor, "source_ip", None),
            actor_source_kind=_normalized(getattr(block.actor, "source_kind", "")),
            actor_login_snapshot=_normalized(getattr(block.actor, "login_snapshot", "")),
            actor_email_snapshot=_normalized(getattr(block.actor, "email_snapshot", "")),
            mode=mode,
            user_id=payload["user_id"] if isinstance(payload["user_id"], int) else None,
            source_ip=str(payload["source_ip"] or ""),
            session_key=str(payload["session_key"] or ""),
            fingerprint=str(payload["fingerprint"] or ""),
            user_agent=str(payload["user_agent"] or ""),
        )
        if best_match is None:
            best_match = match
            continue
        if best_match.mode == SECURITY_BLOCK_MODE_SOFT and match.mode == SECURITY_BLOCK_MODE_HARD:
            best_match = match
            continue
        if best_match.mode == match.mode:
            best_match = match

    if best_match is None:
        cache.set(cache_key, {"none": 1}, timeout=_DECISION_CACHE_TTL_SECONDS)
        return None

    cache.set(
        cache_key,
        {
            "block_id": best_match.block_id,
            "actor_id": best_match.actor_id or "",
            "block_type": best_match.block_type,
            "reason": best_match.reason,
            "expires_at": best_match.expires_at or "",
            "actor_threat_level": best_match.actor_threat_level,
            "actor_source_ip": best_match.actor_source_ip or "",
            "actor_source_kind": best_match.actor_source_kind,
            "actor_login_snapshot": best_match.actor_login_snapshot,
            "actor_email_snapshot": best_match.actor_email_snapshot,
            "mode": best_match.mode,
        },
        timeout=_DECISION_CACHE_TTL_SECONDS,
    )
    return best_match


def serialize_blocked_payload(match: SecurityBlockMatch) -> dict[str, object]:
    return {
        "detail": "Access denied due to active security block.",
        "code": SECURITY_BLOCK_ERROR_CODE,
        "block_id": match.block_id,
        "reason": match.reason,
        "expires_at": match.expires_at,
        "mode": match.mode,
    }


def log_rejected_request(match: SecurityBlockMatch, request) -> None:
    source_material = "|".join(
        [
            match.block_id,
            str(match.user_id or ""),
            match.source_ip,
            match.fingerprint,
            match.session_key,
            str(getattr(request, "path", "") or ""),
            str(getattr(request, "method", "") or ""),
        ]
    )
    cache_key = f"{_CACHE_KEY_LOG_PREFIX}:{_sha(source_material)}"
    try:
        should_log = bool(cache.add(cache_key, "1", timeout=_LOG_THROTTLE_SECONDS))
    except Exception:
        should_log = True
    if not should_log:
        return

    SecurityEvent.objects.create(
        actor_id=match.actor_id,
        event_type="request_rejected_by_block",
        severity=match.actor_threat_level,
        source_ip=match.source_ip or match.actor_source_ip,
        source_kind=match.actor_source_kind,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        login_snapshot=match.actor_login_snapshot,
        email_snapshot=match.actor_email_snapshot,
        method=str(getattr(request, "method", "") or ""),
        endpoint=str(getattr(request, "path", "") or "")[:512],
        status_code=403,
        user_agent=match.user_agent,
        fingerprint=match.fingerprint,
        session_key=match.session_key,
        rule="security_block_enforcement",
        metadata={
            "block_id": match.block_id,
            "block_type": match.block_type,
            "block_mode": match.mode,
        },
        actor_type=SecurityEvent.ACTOR_USER if getattr(request.user, "is_authenticated", False) else SecurityEvent.ACTOR_ANONYMOUS,
    )
