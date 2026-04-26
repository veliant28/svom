#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from apps.autocatalog.models import CarModification  # noqa: E402
from apps.supplier_imports.selectors import get_supplier_integration_by_code  # noqa: E402


def normalize_text(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = raw.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_engine_codes(raw: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", str(raw or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    parts = re.findall(r"[A-Za-z0-9.\-]+", ascii_text)
    codes: set[str] = set()
    for part in parts:
        token = re.sub(r"[^a-z0-9]", "", part.lower())
        if len(token) < 4:
            continue
        if not any(ch.isdigit() for ch in token):
            continue
        codes.add(token)
        if token.startswith("ar") and len(token) > 4:
            codes.add(token[2:])
    return codes


def parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"present", "current", "now", "-", "null", "none"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class LocalRowMeta:
    row: CarModification
    norm_modification: str
    engine_codes: set[str]


class UtrHttpError(RuntimeError):
    def __init__(self, *, code: int, url: str, body: str):
        self.code = int(code)
        self.url = str(url)
        self.body = str(body or "")
        super().__init__(f"UTR HTTPError {self.code} for {self.url}: {self.body[:300]}")


RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 530}


class UtrApiClient:
    def __init__(
        self,
        *,
        token: str,
        sleep_seconds: float,
        request_timeout: float,
        max_retries: int,
        retry_backoff_seconds: float,
        base_url: str = "https://order24-api.utr.ua",
    ):
        self.token = token
        self.sleep_seconds = max(float(sleep_seconds), 0.0)
        self.request_timeout = max(float(request_timeout), 1.0)
        self.max_retries = max(int(max_retries), 0)
        self.retry_backoff_seconds = max(float(retry_backoff_seconds), 0.0)
        self.base_url = base_url.rstrip("/")
        self._last_request_at: float | None = None
        self.request_count = 0

    def _reload_token_from_db(self) -> str:
        integration = get_supplier_integration_by_code(source_code="utr")
        return str(integration.access_token or "").strip()

    def _recover_token_via_auth(self) -> tuple[str, str]:
        try:
            from apps.supplier_imports.services.integrations.utr.client import UtrClient

            client = UtrClient(base_url=self.base_url)
            token, method = client._recover_access_token_for_utr()
            return str(token or "").strip(), str(method or "").strip()
        except Exception as exc:
            print(f"[auth] token recovery failed: {exc}")
            return "", ""

    def _recover_from_401(self, *, body: str) -> bool:
        current_token = str(self.token or "").strip()
        db_token = self._reload_token_from_db()
        if db_token and db_token != current_token:
            self.token = db_token
            print("[auth] 401 detected: reloaded newer token from DB, retrying request")
            return True

        recovered_token, method = self._recover_token_via_auth()
        if recovered_token and recovered_token != current_token:
            self.token = recovered_token
            method_label = method or "recovery"
            print(f"[auth] 401 detected: recovered token via {method_label}, retrying request")
            return True

        if "Invalid JWT Token" in body:
            print("[auth] 401 Invalid JWT Token: auto-recovery did not produce a new token")
        return False

    def _respect_rate_limit(self) -> None:
        if self._last_request_at is None or self.sleep_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.sleep_seconds:
            wait_for = self.sleep_seconds - elapsed
            print(f"[rate-limit] sleep {wait_for:.1f}s before next UTR request")
            time.sleep(wait_for)

    def _retry_wait_seconds(self, attempt: int) -> float:
        return max(self.retry_backoff_seconds * attempt, self.sleep_seconds)

    def get_json(self, path: str) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        auth_recovery_attempted = False

        for attempt in range(1, self.max_retries + 2):
            self._respect_rate_limit()
            print(f"[request #{self.request_count + 1}] GET {url} (attempt {attempt}/{self.max_retries + 1})")
            req = Request(url, headers={"Authorization": f"Bearer {self.token}"})

            try:
                with urlopen(req, timeout=self.request_timeout) as response:
                    payload = response.read().decode("utf-8", "ignore")
                    status = response.status
            except HTTPError as exc:
                self._last_request_at = time.monotonic()
                body = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else ""
                if exc.code == 401 and not auth_recovery_attempted:
                    auth_recovery_attempted = True
                    if self._recover_from_401(body=body):
                        continue
                if exc.code in RETRYABLE_HTTP_CODES and attempt <= self.max_retries:
                    wait_for = self._retry_wait_seconds(attempt)
                    print(f"[http {exc.code}] {url} -> sleep {wait_for:.1f}s before conservative retry")
                    time.sleep(wait_for)
                    continue
                raise UtrHttpError(code=exc.code, url=url, body=body) from exc
            except TimeoutError as exc:
                self._last_request_at = time.monotonic()
                if attempt > self.max_retries:
                    raise RuntimeError(
                        f"UTR request timed out for {url} after {attempt} attempt(s); "
                        f"timeout={self.request_timeout:.0f}s"
                    ) from exc
                wait_for = self._retry_wait_seconds(attempt)
                print(f"[timeout] {url} -> sleep {wait_for:.1f}s before conservative retry")
                time.sleep(wait_for)
                continue
            except URLError as exc:
                self._last_request_at = time.monotonic()
                if attempt > self.max_retries:
                    raise RuntimeError(f"UTR URLError for {url}: {exc}") from exc
                wait_for = self._retry_wait_seconds(attempt)
                print(f"[network] {url} -> sleep {wait_for:.1f}s before conservative retry: {exc}")
                time.sleep(wait_for)
                continue

            self._last_request_at = time.monotonic()
            self.request_count += 1

            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"UTR returned non-JSON response for {url} (status={status})") from exc

        raise RuntimeError(f"UTR request failed unexpectedly for {url}")


@dataclass
class Stats:
    makes_total: int = 0
    makes_matched: int = 0
    models_total: int = 0
    models_matched: int = 0
    rows_scanned: int = 0
    rows_matched: int = 0
    rows_updated: int = 0


def pick_single_id_by_name(items: list[dict], target_name: str) -> int | None:
    target_norm = normalize_text(target_name)
    candidates = [item for item in items if normalize_text(str(item.get("name") or "")) == target_norm]
    if not candidates:
        return None
    candidates.sort(key=lambda item: int(item.get("id") or 0))
    return int(candidates[0].get("id"))


def build_local_index(rows: list[CarModification]) -> list[LocalRowMeta]:
    metas: list[LocalRowMeta] = []
    for row in rows:
        metas.append(
            LocalRowMeta(
                row=row,
                norm_modification=normalize_text(row.modification),
                engine_codes=extract_engine_codes(row.engine),
            )
        )
    return metas


def _name_variants_for_match(*, make_name: str, model_name: str, utr_name: str) -> set[str]:
    full = normalize_text(utr_name)
    variants: set[str] = {full}
    prefixes = [
        normalize_text(f"{make_name} {model_name}"),
        normalize_text(model_name),
        normalize_text(make_name),
    ]
    for prefix in prefixes:
        if not prefix:
            continue
        if full.startswith(prefix + " "):
            tail = full[len(prefix) :].strip()
            if tail:
                variants.add(tail)
    return {item for item in variants if item}


def find_matches(
    local_rows: list[LocalRowMeta],
    *,
    make_name: str,
    model_name: str,
    utr_name: str,
    utr_engine_codes: set[str],
    utr_hp: int | None,
    utr_start: date | None,
) -> list[CarModification]:
    variants = _name_variants_for_match(make_name=make_name, model_name=model_name, utr_name=utr_name)
    if not variants:
        return []

    candidates = [meta for meta in local_rows if meta.norm_modification in variants]
    if not candidates:
        candidates = [
            meta
            for meta in local_rows
            if any(variant.endswith(meta.norm_modification) for variant in variants if meta.norm_modification)
        ]
    if not candidates:
        return []

    if utr_start is not None:
        narrowed = [meta for meta in candidates if meta.row.start_date_at == utr_start]
        if narrowed:
            candidates = narrowed

    if utr_hp is not None:
        narrowed = [meta for meta in candidates if meta.row.hp_from == utr_hp]
        if narrowed:
            candidates = narrowed

    if utr_engine_codes:
        narrowed = [meta for meta in candidates if meta.engine_codes & utr_engine_codes]
        if narrowed:
            candidates = narrowed

    return [meta.row for meta in candidates]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill CarModification.end_date_at from UTR TecDoc yearTo only.")
    parser.add_argument("--make", action="append", default=[], help="Filter by exact make name. Repeatable.")
    parser.add_argument("--model", action="append", default=[], help="Filter by exact model name. Repeatable.")
    parser.add_argument(
        "--resume-make",
        default="",
        help="Resume from this make name (inclusive, lexical order of local makes).",
    )
    parser.add_argument(
        "--resume-model",
        default="",
        help="When --resume-make is set, resume from this model name within that make (inclusive).",
    )
    parser.add_argument("--sleep-seconds", type=float, default=30.0, help="Pause between UTR requests (default: 30).")
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=60.0,
        help="Per-request read timeout in seconds (default: 60, conservative to reduce retries).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retries for timeout/network errors (default: 2, conservative).",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=90.0,
        help="Base sleep before retry after timeout/network errors (default: 90, conservative).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write DB changes.")
    parser.add_argument(
        "--all-rows",
        action="store_true",
        help="Update rows even if end_date_at is already set (default: only rows with end_date_at IS NULL).",
    )
    parser.add_argument("--max-makes", type=int, default=0, help="Limit makes for manual run/debug.")
    parser.add_argument("--max-models-per-make", type=int, default=0, help="Limit models per make for manual run/debug.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.resume_make = str(args.resume_make or "").strip()
    args.resume_model = str(args.resume_model or "").strip()
    if args.resume_model and not args.resume_make:
        print("[error] --resume-model requires --resume-make")
        return 1

    integration = get_supplier_integration_by_code(source_code="utr")
    token = str(integration.access_token or "").strip()
    if not token:
        print("[error] UTR access token is empty")
        return 1

    base_qs = CarModification.objects.select_related("make", "model")
    if not args.all_rows:
        base_qs = base_qs.filter(end_date_at__isnull=True)
    if args.make:
        base_qs = base_qs.filter(make__name__in=args.make)
    if args.model:
        base_qs = base_qs.filter(model__name__in=args.model)

    rows = list(base_qs.order_by("make__name", "model__name", "id"))
    if not rows:
        print("[done] No local rows for selected filters")
        return 0

    grouped: dict[str, dict[str, list[CarModification]]] = {}
    for row in rows:
        grouped.setdefault(row.make.name, {}).setdefault(row.model.name, []).append(row)

    make_names = sorted(grouped.keys())
    if args.resume_make:
        make_names = [name for name in make_names if name >= args.resume_make]
    if args.max_makes and args.max_makes > 0:
        make_names = make_names[: args.max_makes]

    client = UtrApiClient(
        token=token,
        sleep_seconds=args.sleep_seconds,
        request_timeout=args.request_timeout,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )
    stats = Stats(makes_total=len(make_names))

    manufacturers_payload = client.get_json("/tecdoc/manufacturers")
    if not isinstance(manufacturers_payload, list):
        print("[error] Unexpected manufacturers payload type")
        return 1
    manufacturers = [item for item in manufacturers_payload if isinstance(item, dict) and item.get("id")]

    for make_name in make_names:
        local_models_map = grouped[make_name]
        manufacturer_id = pick_single_id_by_name(manufacturers, make_name)
        if manufacturer_id is None:
            print(f"[skip make] {make_name}: not found in UTR manufacturers")
            continue

        stats.makes_matched += 1
        print(f"\n[make] {make_name} -> manufacturer_id={manufacturer_id}")

        models_payload = client.get_json(f"/tecdoc/manufacturers/{manufacturer_id}/models")
        if not isinstance(models_payload, list):
            print(f"[skip make] {make_name}: unexpected models payload")
            continue

        models = [item for item in models_payload if isinstance(item, dict) and item.get("id")]
        local_model_names = sorted(local_models_map.keys())
        if args.resume_make and args.resume_model and make_name == args.resume_make:
            local_model_names = [name for name in local_model_names if name >= args.resume_model]
        if args.max_models_per_make and args.max_models_per_make > 0:
            local_model_names = local_model_names[: args.max_models_per_make]

        stats.models_total += len(local_model_names)

        for model_name in local_model_names:
            model_id = pick_single_id_by_name(models, model_name)
            if model_id is None:
                print(f"  [skip model] {model_name}: not found in UTR models")
                continue

            stats.models_matched += 1
            local_rows = local_models_map[model_name]
            local_index = build_local_index(local_rows)

            try:
                model_payload = client.get_json(f"/tecdoc/manufacturers/{manufacturer_id}/models/{model_id}")
            except UtrHttpError as exc:
                if exc.code == 404 and "Modifications not found" in exc.body:
                    print(f"  [skip model] {model_name}: UTR says modifications not found (404)")
                    continue
                raise
            modifications = []
            if isinstance(model_payload, dict) and isinstance(model_payload.get("modifications"), list):
                modifications = model_payload["modifications"]
            if not modifications:
                print(f"  [model] {model_name}: no modifications in UTR payload")
                continue

            with_year_to = 0
            matched_here = 0
            updated_here = 0
            ambiguous_rows = 0
            proposed_dates_by_row: dict[int, set[date]] = {}
            row_by_id: dict[int, CarModification] = {}

            for item in modifications:
                if not isinstance(item, dict):
                    continue
                end_date = parse_iso_date(item.get("yearTo"))
                if end_date is None:
                    continue
                with_year_to += 1

                name = str(item.get("name") or "").strip()
                if not name:
                    continue

                hp = item.get("powerHP")
                try:
                    hp_int = int(hp) if hp is not None and str(hp).strip() != "" else None
                except Exception:
                    hp_int = None

                start_date = parse_iso_date(item.get("yearFrom"))
                engine_codes = extract_engine_codes(str(item.get("motorCodes") or ""))

                matched_rows = find_matches(
                    local_index,
                    make_name=make_name,
                    model_name=model_name,
                    utr_name=name,
                    utr_engine_codes=engine_codes,
                    utr_hp=hp_int,
                    utr_start=start_date,
                )
                if not matched_rows:
                    continue

                for row in matched_rows:
                    row_by_id[row.id] = row
                    proposed_dates_by_row.setdefault(row.id, set()).add(end_date)

            for row_id, date_set in sorted(proposed_dates_by_row.items()):
                row = row_by_id[row_id]
                stats.rows_scanned += 1
                matched_here += 1
                stats.rows_matched += 1

                if len(date_set) != 1:
                    ambiguous_rows += 1
                    print(
                        f"    [ambiguous] id={row.id} {row.make.name} {row.model.name} | "
                        f"{row.modification} | possible_end_dates={sorted(date_set)}"
                    )
                    continue

                end_date = next(iter(date_set))
                if row.end_date_at == end_date:
                    continue

                if args.dry_run:
                    updated_here += 1
                    stats.rows_updated += 1
                    print(
                        f"    [dry-run update] id={row.id} {row.make.name} {row.model.name} "
                        f"| {row.modification} | {row.end_date_at} -> {end_date}"
                    )
                else:
                    row.end_date_at = end_date
                    row.save(update_fields=["end_date_at", "updated_at"])
                    updated_here += 1
                    stats.rows_updated += 1
                    print(
                        f"    [updated] id={row.id} {row.make.name} {row.model.name} "
                        f"| {row.modification} -> {end_date}"
                    )

            print(
                f"  [model] {model_name}: local_rows={len(local_rows)}, utr_mods={len(modifications)}, "
                f"utr_with_yearTo={with_year_to}, matched={matched_here}, ambiguous={ambiguous_rows}, updated={updated_here}"
            )

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print("\n[summary] mode=", mode)
    print(f"  makes_total={stats.makes_total} makes_matched={stats.makes_matched}")
    print(f"  models_total={stats.models_total} models_matched={stats.models_matched}")
    print(f"  rows_matched={stats.rows_matched} rows_updated={stats.rows_updated}")
    print(f"  utr_requests={client.request_count} sleep_seconds={args.sleep_seconds}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
