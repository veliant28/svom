from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyResult, AutoDbLookupV3ReadOnlyService


@dataclass(frozen=True)
class LookupInput:
    brand: str
    article: str
    note: str
    sample_source: str


class Command(BaseCommand):
    help = "Run Auto_DB lookup v3 diagnostics in read-only mode and export controls/cohort reports."

    CONTROL_BRANDS_FROM_COHORT = ("LEMFORDER", "NURAL", "NTN-SNR", "LOBRO")
    FALLBACK_CONTROL_ARTICLES = {
        "LEMFORDER": "LMI12885",
        "NURAL": "89-336400-10",
        "NTN-SNR": "GA784.04",
        "LOBRO": "301065",
    }

    TARGET_COHORT_BRANDS = ("LEMFORDER", "LESJOFORS", "LOBRO", "NTNSNR", "NURAL")

    def add_arguments(self, parser):
        parser.add_argument(
            "--post-alias-csv",
            type=str,
            default="/tmp/post_alias_50_miss_diagnosis.csv",
            help="Existing post-alias miss cohort CSV (50 rows preferred).",
        )
        parser.add_argument(
            "--controls-csv-out",
            type=str,
            default="/tmp/autodb_lookup_v3_control_results.csv",
        )
        parser.add_argument(
            "--controls-md-out",
            type=str,
            default="/tmp/autodb_lookup_v3_control_results.md",
        )
        parser.add_argument(
            "--cohort-csv-out",
            type=str,
            default="/tmp/post_alias_50_lookup_v3_results.csv",
        )
        parser.add_argument(
            "--cohort-md-out",
            type=str,
            default="/tmp/post_alias_50_lookup_v3_summary.md",
        )
        parser.add_argument(
            "--impact-md-out",
            type=str,
            default="/tmp/autodb_lookup_v3_impact_plan.md",
        )
        parser.add_argument(
            "--queue-size",
            type=int,
            default=14822,
            help="Queue size used for impact simulation.",
        )

    def handle(self, *args, **options):
        post_alias_csv = Path(str(options["post_alias_csv"]).strip()).expanduser()
        controls_csv_out = Path(str(options["controls_csv_out"]).strip()).expanduser()
        controls_md_out = Path(str(options["controls_md_out"]).strip()).expanduser()
        cohort_csv_out = Path(str(options["cohort_csv_out"]).strip()).expanduser()
        cohort_md_out = Path(str(options["cohort_md_out"]).strip()).expanduser()
        impact_md_out = Path(str(options["impact_md_out"]).strip()).expanduser()
        queue_size = max(int(options.get("queue_size") or 0), 0)

        service = AutoDbLookupV3ReadOnlyService()
        cohort_rows = self._load_post_alias_rows(post_alias_csv)

        controls = self._build_controls(post_alias_rows=cohort_rows)
        control_results = self._run_lookup(service=service, rows=controls, run_group="controls")
        self._write_csv(controls_csv_out, control_results)
        self._write_controls_md(path=controls_md_out, results=control_results)

        cohort_inputs = self._build_target_cohort(post_alias_rows=cohort_rows)
        cohort_results = self._run_lookup(service=service, rows=cohort_inputs, run_group="post_alias_50")
        self._write_csv(cohort_csv_out, cohort_results)
        cohort_summary = self._write_cohort_md(path=cohort_md_out, results=cohort_results, input_path=post_alias_csv)

        self._write_impact_md(
            path=impact_md_out,
            queue_size=queue_size,
            cohort_checked=cohort_summary["checked"],
            cohort_hits=cohort_summary["hits"],
            cohort_errors=cohort_summary["errors"],
            brand_stats=cohort_summary["brand_stats"],
        )

        self.stdout.write("Auto_DB lookup v3 read-only diagnostics completed.")
        self.stdout.write(f"- controls_csv: {controls_csv_out}")
        self.stdout.write(f"- controls_md: {controls_md_out}")
        self.stdout.write(f"- cohort_csv: {cohort_csv_out}")
        self.stdout.write(f"- cohort_md: {cohort_md_out}")
        self.stdout.write(f"- impact_md: {impact_md_out}")

    def _load_post_alias_rows(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [self._normalize_row(row) for row in reader]

    def _normalize_row(self, row: dict[str, str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, value in row.items():
            out[str(key or "").strip()] = str(value or "").strip()
        return out

    def _build_controls(self, *, post_alias_rows: list[dict[str, str]]) -> list[LookupInput]:
        controls: list[LookupInput] = [
            LookupInput(brand="OPTIBELT", article="4PK813", note="fixed control: expected remote style 4 PK 813", sample_source="fixed"),
            LookupInput(brand="LESJOFORS", article="77816", note="fixed control from post-alias evidence", sample_source="fixed"),
            LookupInput(brand="NGK", article="0934", note="sanity control expected to exist", sample_source="fixed"),
        ]
        sampled = self._first_article_by_brand(post_alias_rows=post_alias_rows)
        for brand in self.CONTROL_BRANDS_FROM_COHORT:
            article = sampled.get(brand) or self.FALLBACK_CONTROL_ARTICLES.get(brand, "")
            if not article:
                continue
            controls.append(
                LookupInput(
                    brand=brand,
                    article=article,
                    note="sample from post-alias cohort",
                    sample_source="post_alias_csv" if sampled.get(brand) else "fallback",
                )
            )
        return controls

    def _first_article_by_brand(self, *, post_alias_rows: list[dict[str, str]]) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in post_alias_rows:
            brand = self._brand_key(row.get("raw_brand", ""))
            article = (row.get("raw_article") or row.get("supplier_sku") or "").strip()
            if brand and article and brand not in out:
                out[brand] = article
        return out

    def _build_target_cohort(self, *, post_alias_rows: list[dict[str, str]]) -> list[LookupInput]:
        if post_alias_rows:
            filtered = [row for row in post_alias_rows if self._brand_key(row.get("raw_brand", "")) in self.TARGET_COHORT_BRANDS]
            if len(filtered) >= 50:
                selected = filtered[:50]
            else:
                selected = self._reconstruct_10_per_brand(filtered)
            return [
                LookupInput(
                    brand=row.get("raw_brand", ""),
                    article=(row.get("raw_article") or row.get("supplier_sku") or ""),
                    note="post_alias_50_miss_diagnosis.csv",
                    sample_source="post_alias_csv",
                )
                for row in selected
                if row.get("raw_brand") and (row.get("raw_article") or row.get("supplier_sku"))
            ]

        reconstructed: list[LookupInput] = []
        for brand in self.TARGET_COHORT_BRANDS:
            fallback_brand = "NTN-SNR" if brand == "NTNSNR" else brand
            article = self.FALLBACK_CONTROL_ARTICLES.get(fallback_brand) or "UNKNOWN"
            reconstructed.append(
                LookupInput(
                    brand=fallback_brand,
                    article=article,
                    note="fallback cohort reconstruction (source csv missing)",
                    sample_source="fallback",
                )
            )
        return reconstructed

    def _reconstruct_10_per_brand(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        by_brand: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_brand[self._brand_key(row.get("raw_brand", ""))].append(row)
        out: list[dict[str, str]] = []
        for brand in self.TARGET_COHORT_BRANDS:
            out.extend(by_brand.get(brand, [])[:10])
        return out

    def _run_lookup(
        self,
        *,
        service: AutoDbLookupV3ReadOnlyService,
        rows: list[LookupInput],
        run_group: str,
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for index, row in enumerate(rows, start=1):
            brand = str(row.brand or "").strip()
            article = str(row.article or "").strip()
            if not brand or not article:
                continue
            result = service.lookup(brand=brand, article=article)
            out.append(self._to_export_row(index=index, run_group=run_group, row=row, result=result))
        return out

    def _to_export_row(
        self,
        *,
        index: int,
        run_group: str,
        row: LookupInput,
        result: AutoDbLookupV3ReadOnlyResult,
    ) -> dict[str, str]:
        return {
            "row_no": str(index),
            "run_group": run_group,
            "brand": row.brand,
            "raw_article": row.article,
            "note": row.note,
            "sample_source": row.sample_source,
            "status": "found" if result.found else "not_found",
            "supplier_id": str(result.supplier_id or ""),
            "supplier_name": result.supplier_name,
            "supplier_reason": result.supplier_reason,
            "canonical_article": result.canonical_article,
            "remote_stored_article": result.remote_stored_article,
            "matched_table": result.matched_table,
            "matched_source": result.matched_source,
            "local_hits": str(result.local_hits),
            "remote_hits": str(result.remote_hits),
            "article_prd_rows": str(result.article_prd_rows),
            "article_links_rows": str(result.article_links_rows),
            "prd_rows": str(result.prd_rows),
            "prd_article_linkage_presence": "1" if result.linkage_present else "0",
            "remote_queries": str(result.remote_queries),
            "source_path": result.path,
            "endpoint": result.endpoint,
            "error": result.error,
        }

    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "row_no",
            "run_group",
            "brand",
            "raw_article",
            "note",
            "sample_source",
            "status",
            "supplier_id",
            "supplier_name",
            "supplier_reason",
            "canonical_article",
            "remote_stored_article",
            "matched_table",
            "matched_source",
            "local_hits",
            "remote_hits",
            "article_prd_rows",
            "article_links_rows",
            "prd_rows",
            "prd_article_linkage_presence",
            "remote_queries",
            "source_path",
            "endpoint",
            "error",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fields})

    def _write_controls_md(self, *, path: Path, results: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        lines.append("# Auto_DB lookup v3 control results")
        lines.append("")
        lines.append("| brand | article | status | supplier_id | canonical | remote_stored | matched_source | matched_table | linkage | remote_hits | error |")
        lines.append("|---|---|---|---:|---|---|---|---|---|---:|---|")
        for row in results:
            lines.append(
                "| {brand} | {raw_article} | {status} | {supplier_id} | {canonical_article} | {remote_stored_article} | "
                "{matched_source} | {matched_table} | {prd_article_linkage_presence} | {remote_hits} | {error} |".format(**row)
            )
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def _write_cohort_md(self, *, path: Path, results: list[dict[str, str]], input_path: Path) -> dict[str, object]:
        path.parent.mkdir(parents=True, exist_ok=True)
        checked = len(results)
        hits = sum(1 for row in results if row.get("status") == "found")
        errors = sum(1 for row in results if row.get("error"))
        still_not_found = checked - hits
        false_not_found_recovered = hits

        brand_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"checked": 0, "hits": 0, "errors": 0})
        for row in results:
            brand = self._brand_key(row.get("brand", "")) or row.get("brand", "")
            brand_counts[brand]["checked"] += 1
            if row.get("status") == "found":
                brand_counts[brand]["hits"] += 1
            if row.get("error"):
                brand_counts[brand]["errors"] += 1

        lines: list[str] = []
        lines.append("# Post-alias 50 lookup v3 summary")
        lines.append("")
        lines.append(f"- source_csv: {input_path}")
        lines.append(f"- checked: {checked}")
        lines.append(f"- hits: {hits}")
        lines.append(f"- false_not_found_recovered: {false_not_found_recovered}")
        lines.append(f"- still_not_found: {still_not_found}")
        lines.append(f"- errors: {errors}")
        lines.append("")
        lines.append("## Hit rate by brand")
        lines.append("")
        lines.append("| brand | checked | hits | still_not_found | errors | hit_rate |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for brand in sorted(brand_counts.keys()):
            checked_brand = brand_counts[brand]["checked"]
            hits_brand = brand_counts[brand]["hits"]
            errors_brand = brand_counts[brand]["errors"]
            miss_brand = checked_brand - hits_brand
            hit_rate = (hits_brand / checked_brand) if checked_brand else 0.0
            lines.append(
                f"| {brand} | {checked_brand} | {hits_brand} | {miss_brand} | {errors_brand} | {hit_rate:.2%} |"
            )
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

        return {
            "checked": checked,
            "hits": hits,
            "errors": errors,
            "brand_stats": brand_counts,
        }

    def _write_impact_md(
        self,
        *,
        path: Path,
        queue_size: int,
        cohort_checked: int,
        cohort_hits: int,
        cohort_errors: int,
        brand_stats: dict[str, dict[str, int]],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        recovery_rate = (cohort_hits / cohort_checked) if cohort_checked else 0.0
        estimated_invalid_not_found = int(round(queue_size * recovery_rate))
        estimated_confirmed_not_found = max(queue_size - estimated_invalid_not_found, 0)
        error_rate = (cohort_errors / cohort_checked) if cohort_checked else 0.0

        if error_rate >= 0.20:
            recommended_batch = 100
        elif error_rate >= 0.10:
            recommended_batch = 200
        else:
            recommended_batch = 300

        lines: list[str] = []
        lines.append("# Auto_DB lookup v3 impact simulation plan")
        lines.append("")
        lines.append("## Inputs")
        lines.append(f"- post_alias_queue_pairs: {queue_size}")
        lines.append(f"- sampled_checked: {cohort_checked}")
        lines.append(f"- sampled_hits_recovered: {cohort_hits}")
        lines.append(f"- sampled_errors: {cohort_errors}")
        lines.append(f"- sampled_recovery_rate: {recovery_rate:.2%}")
        lines.append(f"- sampled_error_rate: {error_rate:.2%}")
        lines.append("")
        lines.append("## Estimated impact")
        lines.append(f"- estimated_previous_not_found_invalid: {estimated_invalid_not_found}")
        lines.append(f"- estimated_still_not_found_after_v3: {estimated_confirmed_not_found}")
        lines.append("")
        lines.append("## Recommended next controlled batch")
        lines.append(f"- batch_size: {recommended_batch}")
        lines.append("- selection: keep strict canonical supplier_id + canonical_article only")
        lines.append("- ordering: start with brands showing highest recovered rate in sample")
        lines.append("")
        lines.append("## Safe state handling")
        lines.append("- keep read-only lookup phase separated from any linking/import flow")
        lines.append("- persist lookup status as diagnostics only; do not mutate Product/SupplierOffer/ProductPrice")
        lines.append("- classify rows into found / not_found / error and retry only error rows")
        lines.append("")
        lines.append("## Quota strategy")
        lines.append("- cap remote queries per item and keep article_numbers -> articles order")
        lines.append("- run in short waves with cool-down when remote errors rise")
        lines.append("- backoff and retry on remote quota/connection exceptions")
        lines.append("- avoid broad scans; query exact supplier_id + variant only")
        lines.append("")
        lines.append("## Brand sample stats used")
        for brand in sorted(brand_stats.keys()):
            stats = brand_stats[brand]
            checked = int(stats.get("checked") or 0)
            hits = int(stats.get("hits") or 0)
            rate = (hits / checked) if checked else 0.0
            lines.append(f"- {brand}: checked={checked}, hits={hits}, hit_rate={rate:.2%}")

        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def _brand_key(self, brand: str) -> str:
        value = str(brand or "").strip().upper().replace(" ", "")
        if value == "NTN-SNR":
            return "NTNSNR"
        return value
