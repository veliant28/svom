from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.supplier_imports.application.category_mapping_command import (
    CommandOutput,
    SELECTIVE_GUARDRAIL_CODES,
    run_category_mapping_command,
)


class Command(BaseCommand):
    help = "Auto-map supplier raw offers to catalog categories with conservative confidence thresholds."

    def add_arguments(self, parser):
        parser.add_argument(
            "--supplier",
            action="append",
            default=None,
            help="Supplier code filter. Can be passed multiple times.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Iterator chunk size.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional limit for processed rows.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate mapping without saving DB updates.",
        )
        parser.add_argument(
            "--overwrite-manual",
            action="store_true",
            help="Allow overwriting rows with manual_mapped status.",
        )
        parser.add_argument(
            "--force-map-all",
            action="store_true",
            help="Mandatory fallback mode: assign category to every row; low-confidence rows become needs_review.",
        )
        parser.add_argument(
            "--recheck-risky-mappings",
            action="store_true",
            help="Re-check already mapped risky forced rows and downgrade/fix suspicious mappings without creating unmapped rows.",
        )
        parser.add_argument(
            "--recheck-guardrail-codes",
            action="append",
            default=None,
            choices=SELECTIVE_GUARDRAIL_CODES,
            help="Selective guardrail recheck by guardrail code. Can be passed multiple times.",
        )
        parser.add_argument(
            "--recheck-reason",
            action="append",
            default=None,
            help="Optional reason filters for selective recheck. Can be passed multiple times.",
        )
        parser.add_argument(
            "--recheck-category-name",
            action="append",
            default=None,
            help="Optional mapped category name contains filters for selective recheck.",
        )
        parser.add_argument(
            "--recheck-title-pattern",
            action="append",
            default=None,
            help="Optional product_name contains filters for selective recheck.",
        )

    def handle(self, *args, **options):
        run_category_mapping_command(
            raw_options=options,
            output=CommandOutput(
                write=self.stdout.write,
                success=self.style.SUCCESS,
                warning=self.style.WARNING,
            ),
        )
