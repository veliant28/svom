from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.autodb.services.lookup_v3_readonly import AutoDbLookupV3ReadOnlyService
from apps.autodb.services.matching.pipeline import AutoDbMatchingPipelineService


class Command(BaseCommand):
    help = "Run read-only UTR micro-smoke for FEBI BILSTEIN / 01111 and evaluate pilot pre-gate eligibility."

    def add_arguments(self, parser):
        parser.add_argument("--brand", type=str, default="FEBI BILSTEIN")
        parser.add_argument("--article", type=str, default="01111")
        parser.add_argument("--min-probe-n", type=int, default=20)
        parser.add_argument("--min-hit-rate", type=float, default=20.0)
        parser.add_argument("--export-md", type=str, default="/tmp/utr_febi_01111_micro_smoke_report.md")

    def handle(self, *args, **options):
        brand = str(options.get("brand") or "FEBI BILSTEIN").strip()
        article = str(options.get("article") or "01111").strip()
        min_probe_n = max(int(options.get("min_probe_n") or 20), 1)
        min_hit_rate = float(options.get("min_hit_rate") or 20.0)
        export_md = Path(str(options.get("export_md") or "/tmp/utr_febi_01111_micro_smoke_report.md")).expanduser()

        lookup = AutoDbLookupV3ReadOnlyService().lookup(brand=brand, article=article)
        hits = 1 if bool(lookup.found) else 0
        eligibility = AutoDbMatchingPipelineService().evaluate_pilot_eligibility(
            candidate_count=1,
            probe_n=1,
            hits=hits,
            min_probe_n=min_probe_n,
            min_hit_rate_pct=min_hit_rate,
        )

        payload = {
            "brand": brand,
            "article": article,
            "found": bool(lookup.found),
            "matched_source": lookup.matched_source,
            "matched_table": lookup.matched_table,
            "supplier_id": lookup.supplier_id,
            "remote_hits": int(lookup.remote_hits or 0),
            "local_hits": int(lookup.local_hits or 0),
            "remote_queries": int(lookup.remote_queries or 0),
            "error": str(lookup.error or ""),
            "micro_smoke_passed": bool(lookup.found),
            "pilot_can_continue": bool(eligibility.can_continue),
            "pilot_reason": str(eligibility.reason),
            "min_probe_n": int(eligibility.min_probe_n),
            "min_hit_rate_pct": float(eligibility.min_hit_rate_pct),
            "probe_n": int(eligibility.probe_n),
            "hit_rate_pct": float(eligibility.hit_rate_pct),
            "db_writes": 0,
        }

        lines = [
            "# UTR FEBI 01111 micro-smoke (read-only)",
            "",
            f"- brand: `{payload['brand']}`",
            f"- article: `{payload['article']}`",
            f"- micro_smoke_passed: `{payload['micro_smoke_passed']}`",
            f"- matched_source: `{payload['matched_source'] or '-'} `",
            f"- matched_table: `{payload['matched_table'] or '-'} `",
            f"- supplier_id: `{payload['supplier_id'] or '-'} `",
            f"- pilot_can_continue: `{payload['pilot_can_continue']}`",
            f"- pilot_reason: `{payload['pilot_reason']}`",
            f"- probe_n / min_probe_n: `{payload['probe_n']} / {payload['min_probe_n']}`",
            f"- hit_rate_pct / min_hit_rate_pct: `{payload['hit_rate_pct']:.2f} / {payload['min_hit_rate_pct']:.2f}`",
            "",
            "## Safety",
            "",
            "- Read-only lookup only.",
            "- No DB writes, no sync/apply/import/enrichment/UTR API.",
            "",
            "```json",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "```",
        ]
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.stdout.write(f"MD export: {export_md}")
        self.stdout.write(json.dumps(payload, ensure_ascii=False))
