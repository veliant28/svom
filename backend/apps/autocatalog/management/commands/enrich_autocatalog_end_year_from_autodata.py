from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone as dt_timezone
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.autocatalog.models import CarModification


AUTODATA_BRAND_URLS = {
    "ALFA ROMEO": "https://www.auto-data.net/en/alfa-romeo-brand-11",
    "ACURA": "https://www.auto-data.net/en/acura-brand-6",
    "AION": "https://www.auto-data.net/en/aion-brand-365",
}

ABS_URL_PREFIX = "https://www.auto-data.net"
HTTP_TIMEOUT_SECONDS = 30
DEFAULT_SLEEP_SECONDS = 0.15

MODEL_LINK_RE = re.compile(
    r'<a class="modeli" href="(?P<href>/en/[^"]+-model-\d+)".*?<strong>(?P<name>[^<]+)</strong>',
    re.IGNORECASE | re.DOTALL,
)
GENERATION_LINK_RE = re.compile(
    r'href="(?P<href>/en/[^"]+-generation-\d+)"',
    re.IGNORECASE,
)
SPEC_ROW_RE = re.compile(
    r'<a href="(?P<href>/en/[^"]+-\d+)"[^>]*>\s*<strong>\s*<span class="tit">(?P<title>.*?)</span>\s*'
    r'<span class="end">(?P<years>.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
ENGINE_CODE_ROW_RE = re.compile(
    r"<tr><th>\s*Engine(?:\s+Model/Code|\s+model/code|\s+code)?\s*</th>\s*<td>(?P<code>.*?)</td>\s*</tr>",
    re.IGNORECASE | re.DOTALL,
)
YEAR_RANGE_RE = re.compile(r"(?P<start>\d{4})\s*-\s*(?P<end>\d{4}|present|current|now)", re.IGNORECASE)
HP_RE = re.compile(r"\((?P<hp>\d+)\s*Hp\)", re.IGNORECASE)
CAPACITY_RE = re.compile(r"(?P<cap>\d+(?:\.\d+)?)")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
PARENS_RE = re.compile(r"\([^)]*\)")
MULTISPACE_RE = re.compile(r"\s+")

DROP_MODEL_TOKENS = {
    "sedan",
    "sportwagon",
    "coupe",
    "spider",
    "berlina",
    "wagon",
    "hatchback",
    "liftback",
    "suv",
    "bus",
    "van",
    "platform",
    "chassis",
    "open",
    "offroad",
    "cabrio",
    "convertible",
    "универсал",
    "універсал",
    "седан",
    "купе",
    "лифтбек",
    "ліфтбек",
    "хетчбек",
    "фургон",
    "автобус",
    "платформа",
    "шасси",
    "шасі",
    "позашляховик",
    "відкритий",
}

STOP_TOKENS = {
    "i",
    "v",
    "the",
    "and",
    "with",
    "hp",
}

BODY_STYLE_TOKENS = {
    "sedan",
    "sportwagon",
    "wagon",
    "estate",
    "coupe",
    "spider",
    "hatchback",
    "liftback",
    "suv",
    "bus",
    "van",
    "platform",
    "chassis",
    "offroad",
}


@dataclass(frozen=True)
class AutoDataSpec:
    model_key: str
    title: str
    url: str
    start_year: int
    end_year: int | None
    hp: int | None
    capacity: float | None
    tokens: frozenset[str]
    engine_codes: frozenset[str]
    body_tokens: frozenset[str]
    transmission_tags: frozenset[str]


class Command(BaseCommand):
    help = _(
        "Дозаполняет end_date_at (год До) для модификаций автокаталога "
        "по интернет-источнику Auto-Data c консервативным матчингом."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--make",
            type=str,
            default="ALFA ROMEO",
            help=_("Марка для обогащения (по умолчанию: ALFA ROMEO)."),
        )
        parser.add_argument(
            "--brand-url",
            type=str,
            default="",
            help=_("Явный URL бренда Auto-Data (опционально, переопределяет внутреннюю карту)."),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Только показать, что будет обновлено, без записи в БД."),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help=_("Ограничить количество строк CarModification для обработки (0 = без лимита)."),
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=DEFAULT_SLEEP_SECONDS,
            help=_("Пауза между HTTP-запросами, сек (по умолчанию 0.15)."),
        )

    def handle(self, *args, **options):
        make = str(options.get("make") or "").strip().upper()
        if not make:
            raise CommandError("Empty --make")
        explicit_brand_url = str(options.get("brand_url") or "").strip()
        brand_url = explicit_brand_url or AUTODATA_BRAND_URLS.get(make)
        if not brand_url:
            raise CommandError(f"Unsupported make for this command: {make}")

        dry_run = bool(options.get("dry_run"))
        limit = int(options.get("limit") or 0)
        sleep_s = float(options.get("sleep") or 0.0)

        timestamp = datetime.now(tz=dt_timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = (Path(settings.BASE_DIR).parent / f"autodata_end_year_report_{make.replace(' ', '_').lower()}_{timestamp}.csv").resolve()

        self.stdout.write(f"Loading source catalog for {make} ...")
        specs = self._load_autodata_specs(brand_url=brand_url, sleep_seconds=sleep_s)
        if not specs:
            raise CommandError(f"No spec entries parsed from {brand_url}")
        self.stdout.write(f"Parsed source specs: {len(specs)}")

        source_by_model: dict[str, list[AutoDataSpec]] = {}
        for spec in specs:
            source_by_model.setdefault(spec.model_key, []).append(spec)

        queryset = (
            CarModification.objects.select_related("make", "model")
            .filter(make__name=make, end_date_at__isnull=True)
            .order_by("id")
        )
        if limit > 0:
            queryset = queryset[:limit]
        local_rows = list(queryset)
        self.stdout.write(f"Local rows to inspect: {len(local_rows)}")

        matched = 0
        updated = 0
        no_model = 0
        no_engine = 0
        ambiguous = 0
        no_match = 0

        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", newline="", encoding="utf-8") as report_file:
            writer = csv.writer(report_file)
            writer.writerow(
                [
                    "car_modification_id",
                    "make",
                    "model",
                    "local_modification",
                    "local_start_date_at",
                    "local_hp",
                    "local_capacity",
                    "local_engine",
                    "match_status",
                    "matched_source_title",
                    "matched_source_years",
                    "matched_source_engine_codes",
                    "matched_source_url",
                    "applied_end_date_at",
                ]
            )

            with transaction.atomic():
                for row in local_rows:
                    model_key = self._normalize_model_name(row.model.name)
                    candidates = source_by_model.get(model_key, [])
                    if not candidates:
                        no_model += 1
                        writer.writerow(
                            [
                                row.id,
                                row.make.name,
                                row.model.name,
                                row.modification,
                                row.start_date_at,
                                row.hp_from,
                                row.capacity,
                                row.engine,
                                "no_model_mapping",
                                "",
                                "",
                                "",
                                "",
                            ]
                        )
                        continue

                    local_engine_codes = self._extract_engine_codes(row.engine)
                    if not local_engine_codes:
                        no_engine += 1
                        writer.writerow(
                            [
                                row.id,
                                row.make.name,
                                row.model.name,
                                row.modification,
                                row.start_date_at,
                                row.hp_from,
                                row.capacity,
                                row.engine,
                                "skip_no_engine_codes",
                                "",
                                "",
                                "",
                                "",
                            ]
                        )
                        continue

                    decision = self._match_modification(row=row, candidates=candidates)
                    if decision is None:
                        no_match += 1
                        writer.writerow(
                            [
                                row.id,
                                row.make.name,
                                row.model.name,
                                row.modification,
                                row.start_date_at,
                                row.hp_from,
                                row.capacity,
                                row.engine,
                                "no_match",
                                "",
                                "",
                                "",
                                "",
                            ]
                        )
                        continue
                    if decision == "ambiguous":
                        ambiguous += 1
                        writer.writerow(
                            [
                                row.id,
                                row.make.name,
                                row.model.name,
                                row.modification,
                                row.start_date_at,
                                row.hp_from,
                                row.capacity,
                                row.engine,
                                "ambiguous",
                                "",
                                "",
                                "",
                                "",
                            ]
                        )
                        continue

                    spec = decision
                    if spec.end_year is None:
                        no_match += 1
                        writer.writerow(
                            [
                                row.id,
                                row.make.name,
                                row.model.name,
                                row.modification,
                                row.start_date_at,
                                row.hp_from,
                                row.capacity,
                                row.engine,
                                "ongoing_or_no_end_year",
                                spec.title,
                                f"{spec.start_year}-present",
                                ",".join(sorted(spec.engine_codes)),
                                spec.url,
                                "",
                            ]
                        )
                        continue

                    if row.start_date_at and spec.end_year < row.start_date_at.year:
                        no_match += 1
                        writer.writerow(
                            [
                                row.id,
                                row.make.name,
                                row.model.name,
                                row.modification,
                                row.start_date_at,
                                row.hp_from,
                                row.capacity,
                                row.engine,
                                "source_end_before_local_start",
                                spec.title,
                                f"{spec.start_year}-{spec.end_year}",
                                ",".join(sorted(spec.engine_codes)),
                                spec.url,
                                "",
                            ]
                        )
                        continue

                    matched += 1
                    applied_date = date(spec.end_year, 12, 31)
                    if not dry_run:
                        row.end_date_at = applied_date
                        row.save(update_fields=["end_date_at", "updated_at"])
                        updated += 1

                    writer.writerow(
                        [
                            row.id,
                            row.make.name,
                            row.model.name,
                            row.modification,
                            row.start_date_at,
                            row.hp_from,
                            row.capacity,
                            row.engine,
                            "matched",
                            spec.title,
                            f"{spec.start_year}-{spec.end_year}",
                            ",".join(sorted(spec.engine_codes)),
                            spec.url,
                            applied_date.isoformat(),
                        ]
                    )

                if dry_run:
                    transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("AutoData enrichment finished"))
        self.stdout.write(f"  make: {make}")
        self.stdout.write(f"  dry_run: {dry_run}")
        self.stdout.write(f"  matched: {matched}")
        self.stdout.write(f"  updated: {updated}")
        self.stdout.write(f"  no_model_mapping: {no_model}")
        self.stdout.write(f"  skip_no_engine_codes: {no_engine}")
        self.stdout.write(f"  ambiguous: {ambiguous}")
        self.stdout.write(f"  no_match_or_skipped: {no_match}")
        self.stdout.write(f"  report: {report_path}")

    def _load_autodata_specs(self, *, brand_url: str, sleep_seconds: float) -> list[AutoDataSpec]:
        specs: list[AutoDataSpec] = []
        seen_generation_urls: set[str] = set()

        brand_html = self._fetch_html(brand_url)
        model_links = self._parse_model_links(brand_html)
        for model_name, model_url in model_links:
            model_key = self._normalize_model_name(model_name)
            if not model_key:
                continue

            time.sleep(max(0.0, sleep_seconds))
            model_html = self._fetch_html(model_url)
            generation_urls = self._parse_generation_urls(model_html)
            for generation_url in generation_urls:
                if generation_url in seen_generation_urls:
                    continue
                seen_generation_urls.add(generation_url)
                time.sleep(max(0.0, sleep_seconds))
                generation_html = self._fetch_html(generation_url)
                for source_title, years_label, spec_url in self._parse_specs_from_generation(generation_html):
                    start_year, end_year = self._parse_year_range(years_label)
                    if start_year is None:
                        continue
                    hp = self._extract_hp(source_title)
                    capacity = self._extract_capacity(source_title)
                    tokens = frozenset(self._tokenize(source_title))
                    time.sleep(max(0.0, sleep_seconds))
                    try:
                        spec_html = self._fetch_html(spec_url)
                    except Exception:  # noqa: BLE001
                        continue
                    engine_codes = frozenset(self._extract_engine_codes_from_spec_html(spec_html))
                    body_tokens = frozenset(self._extract_body_tokens(f"{spec_url} {source_title}"))
                    transmission_tags = frozenset(self._extract_transmission_tags(source_title))
                    specs.append(
                        AutoDataSpec(
                            model_key=model_key,
                            title=source_title,
                            url=spec_url,
                            start_year=start_year,
                            end_year=end_year,
                            hp=hp,
                            capacity=capacity,
                            tokens=tokens,
                            engine_codes=engine_codes,
                            body_tokens=body_tokens,
                            transmission_tags=transmission_tags,
                        )
                    )
        return specs

    def _fetch_html(self, url: str) -> str:
        normalized_url = self._normalize_url(url)
        request = Request(
            normalized_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SVOMAutocatalogBot/1.0; +https://www.auto-data.net/)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = response.read()
        return payload.decode("utf-8", errors="ignore")

    def _normalize_url(self, url: str) -> str:
        parts = urlsplit(url)
        path = quote(parts.path, safe="/%:@-._~!$&'()*+,;=")
        query = quote(parts.query, safe="=&%:@-._~!$'()*+,;/?")
        fragment = quote(parts.fragment, safe="=&%:@-._~!$'()*+,;/?")
        return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))

    def _parse_model_links(self, html: str) -> list[tuple[str, str]]:
        seen: set[str] = set()
        output: list[tuple[str, str]] = []
        for match in MODEL_LINK_RE.finditer(html):
            name = self._strip_html(match.group("name"))
            href = match.group("href")
            if not name or not href:
                continue
            url = self._abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            output.append((name, url))
        return output

    def _parse_generation_urls(self, html: str) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for match in GENERATION_LINK_RE.finditer(html):
            href = match.group("href")
            if not href:
                continue
            url = self._abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            output.append(url)
        return output

    def _parse_specs_from_generation(self, html: str) -> Iterable[tuple[str, str, str]]:
        for match in SPEC_ROW_RE.finditer(html):
            title = self._strip_html(match.group("title"))
            years = self._strip_html(match.group("years"))
            href = match.group("href")
            if not title or not years or not href:
                continue
            yield title, years, self._abs_url(href)

    def _parse_year_range(self, raw_years: str) -> tuple[int | None, int | None]:
        normalized = raw_years.strip().lower()
        parsed = YEAR_RANGE_RE.search(normalized)
        if not parsed:
            return None, None
        start = int(parsed.group("start"))
        end_text = parsed.group("end")
        if end_text.isdigit():
            return start, int(end_text)
        return start, None

    def _extract_hp(self, title: str) -> int | None:
        parsed = HP_RE.search(title)
        if not parsed:
            return None
        return int(parsed.group("hp"))

    def _extract_capacity(self, title: str) -> float | None:
        parsed = CAPACITY_RE.search(title)
        if not parsed:
            return None
        try:
            return float(parsed.group("cap"))
        except ValueError:
            return None

    def _match_modification(self, *, row: CarModification, candidates: list[AutoDataSpec]) -> AutoDataSpec | str | None:
        local_tokens = set(self._tokenize(row.modification))
        local_engine_codes = self._extract_engine_codes(row.engine)
        local_body_tokens = self._extract_body_tokens(row.model.name)
        local_transmission_tags = self._extract_transmission_tags(row.modification)
        local_drivetrain_tags = self._extract_drivetrain_tags(row.modification)
        local_capacity = self._parse_capacity_from_local(row.capacity)
        local_start_year = row.start_date_at.year if row.start_date_at else None
        local_hp = row.hp_from

        scoped = [c for c in candidates if c.end_year is not None and c.engine_codes]
        if not scoped:
            return None

        scored: list[tuple[tuple[int, int, int, int, int, int, int, int], AutoDataSpec]] = []
        for spec in scoped:
            engine_overlap = len(local_engine_codes & set(spec.engine_codes))
            if engine_overlap == 0:
                continue
            spec_drivetrain_tags = self._extract_drivetrain_tags(spec.title)
            local_is_4x4 = "awd" in local_drivetrain_tags
            spec_is_4x4 = "awd" in spec_drivetrain_tags
            if local_is_4x4 != spec_is_4x4:
                continue
            body_score = 0
            if local_body_tokens:
                if not spec.body_tokens:
                    body_score = 0
                elif local_body_tokens & set(spec.body_tokens):
                    body_score = 1
                else:
                    continue
            else:
                if {"sportwagon", "wagon", "estate"} & set(spec.body_tokens):
                    continue
            # If source candidate explicitly encodes transmission type not present locally, skip it.
            if {"automatic", "qtronic", "selespeed"} & set(spec.transmission_tags):
                if not (set(spec.transmission_tags) & local_transmission_tags):
                    continue
            overlap = len(local_tokens & set(spec.tokens))
            cap_score = 0
            if local_capacity is not None and spec.capacity is not None and abs(local_capacity - spec.capacity) <= 0.11:
                cap_score = 1
            start_score = 0
            start_distance = -9_999
            if local_start_year is not None and abs(spec.start_year - local_start_year) <= 1:
                start_score = 1
            if local_start_year is not None:
                start_distance = -abs(spec.start_year - local_start_year)
            hp_exact = 0
            hp_close = 0
            if local_hp is not None and spec.hp is not None:
                hp_exact = 1 if spec.hp == local_hp else 0
                hp_close = 1 if abs(spec.hp - local_hp) <= 2 else 0
            # When modification labels are localized, token overlap can be zero.
            # Require at least one objective signal besides engine code.
            if overlap == 0 and hp_exact == 0 and hp_close == 0 and cap_score == 0 and start_score == 0:
                continue
            # Higher tuple means better match.
            score = (engine_overlap, overlap, hp_exact, hp_close, cap_score, body_score, start_score, start_distance)
            scored.append((score, spec))

        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_spec = scored[0]

        if len(scored) > 1 and scored[1][0] == best_score:
            same_score_specs = [spec for score, spec in scored if score == best_score]
            end_years = {spec.end_year for spec in same_score_specs}
            if len(end_years) == 1:
                return same_score_specs[0]
            return "ambiguous"
        return best_spec

    def _extract_engine_codes_from_spec_html(self, html: str) -> set[str]:
        match = ENGINE_CODE_ROW_RE.search(html)
        if not match:
            return set()
        raw_value = self._strip_html(match.group("code"))
        return self._extract_engine_codes(raw_value)

    def _extract_engine_codes(self, raw_value: str) -> set[str]:
        normalized = unescape(raw_value or "")
        chunks = re.split(r"[,;/|]+|\s{2,}", normalized)
        codes: set[str] = set()
        for chunk in chunks:
            for token in re.findall(r"[A-Za-z0-9.\-]+", chunk):
                norm = re.sub(r"[^a-z0-9]", "", token.lower())
                if not norm or len(norm) < 4:
                    continue
                if not any(char.isdigit() for char in norm):
                    continue
                codes.add(norm)
                # Family fallback: C30A3 -> C30A, J35A4 -> J35A.
                base = re.sub(r"\d+$", "", norm)
                if base != norm and len(base) >= 4 and any(char.isdigit() for char in base):
                    codes.add(base)
                if norm.startswith("ar") and len(norm) > 4:
                    tail = norm[2:]
                    if any(char.isdigit() for char in tail):
                        codes.add(tail)
        return codes

    def _normalize_model_name(self, model_name: str) -> str:
        normalized = self._normalize_plain_text(model_name)
        tokens = [token for token in normalized.split() if token and token not in DROP_MODEL_TOKENS]
        return " ".join(tokens).strip()

    def _normalize_plain_text(self, value: str) -> str:
        lowered = unescape(value or "").lower()
        lowered = lowered.replace("i.e.", " ie ")
        lowered = lowered.replace("q-tronic", " qtronic ")
        lowered = PARENS_RE.sub(" ", lowered)
        lowered = NON_ALNUM_RE.sub(" ", lowered)
        lowered = MULTISPACE_RE.sub(" ", lowered)
        return lowered.strip()

    def _tokenize(self, value: str) -> list[str]:
        normalized = self._normalize_plain_text(value)
        if not normalized:
            return []
        return [token for token in normalized.split() if len(token) >= 2 and token not in STOP_TOKENS]

    def _extract_body_tokens(self, value: str) -> set[str]:
        normalized = self._normalize_plain_text(value)
        if not normalized:
            return set()
        tokens = set(normalized.split())
        if "sportwagon" in tokens:
            tokens.add("wagon")
            tokens.add("estate")
        # Normalize common aliases.
        if "station" in tokens and "wagon" in tokens:
            tokens.add("sportwagon")
            tokens.add("wagon")
            tokens.add("estate")
        if "estate" in tokens:
            tokens.add("wagon")
            tokens.add("sportwagon")
        return {token for token in tokens if token in BODY_STYLE_TOKENS}

    def _extract_transmission_tags(self, value: str) -> set[str]:
        lowered = unescape(value or "").lower()
        normalized = lowered.replace("-", " ")
        tags: set[str] = set()
        if "q tronic" in normalized or "qtronic" in normalized:
            tags.add("qtronic")
            tags.add("automatic")
        if "selespeed" in normalized:
            tags.add("selespeed")
            tags.add("automatic")
        if "automatic" in normalized:
            tags.add("automatic")
        if "manual" in normalized:
            tags.add("manual")
        return tags

    def _extract_drivetrain_tags(self, value: str) -> set[str]:
        normalized = self._normalize_plain_text(value)
        if not normalized:
            return set()
        tags: set[str] = set()
        compact = normalized.replace(" ", "")
        if "4x4" in compact or "4wd" in compact or "awd" in compact:
            tags.add("awd")
        return tags

    def _parse_capacity_from_local(self, raw_capacity: str) -> float | None:
        parsed = CAPACITY_RE.search(raw_capacity or "")
        if not parsed:
            return None
        try:
            return float(parsed.group("cap"))
        except ValueError:
            return None

    def _abs_url(self, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if not href.startswith("/"):
            href = f"/{href}"
        return f"{ABS_URL_PREFIX}{href}"

    def _strip_html(self, value: str) -> str:
        no_tags = re.sub(r"<[^>]+>", " ", value or "")
        no_tags = unescape(no_tags)
        no_tags = MULTISPACE_RE.sub(" ", no_tags)
        return no_tags.strip()
