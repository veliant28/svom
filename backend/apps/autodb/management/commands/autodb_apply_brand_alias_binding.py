from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.remaining_alias_binding import AutoDbRemainingAliasBindingService


class Command(BaseCommand):
    help = 'Apply remaining brand-level Auto_DB supplier alias binding through matching service.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False)
        parser.add_argument('--queue-limit', type=int, default=50000)

    def handle(self, *args, **options):
        apply_changes = bool(options.get('apply'))
        queue_limit = int(options.get('queue_limit') or 50000)
        service = AutoDbRemainingAliasBindingService()
        payload = service.run(apply_changes=apply_changes, queue_limit=queue_limit)

        self.stdout.write('Done')
        self.stdout.write(f"apply_changes={apply_changes}")
        self.stdout.write(f"queue_limit={queue_limit}")
        self.stdout.write(f"applied_aliases={payload.get('apply_summary', {}).get('aliases_created', 0)}")
        self.stdout.write(f"applied_product_rows={payload.get('apply_summary', {}).get('product_rows_bound', 0)}")
