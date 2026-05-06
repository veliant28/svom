from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deprecated wrapper. Use autodb_clone_sync --vehicle-catalog instead."

    def add_arguments(self, parser):
        parser.add_argument("--only", type=str, default="")
        parser.add_argument("--batch-size", type=int, default=0)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--start-from-id", type=int, default=0)

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("autodb_sync_vehicle_catalog is deprecated; using autodb_clone_sync --vehicle-catalog"))

        kwargs = {
            "vehicle_catalog": True,
            "resume": bool(options.get("resume")),
            "dry_run": bool(options.get("dry_run")),
            "force_recreate_table": bool(options.get("force")),
        }

        only = str(options.get("only") or "").strip()
        if only:
            kwargs["only"] = only

        batch_size = int(options.get("batch_size") or 0)
        if batch_size > 0:
            kwargs["batch_size"] = batch_size

        limit = int(options.get("limit") or 0)
        if limit > 0:
            kwargs["limit"] = limit

        start_from_id = int(options.get("start_from_id") or 0)
        if start_from_id > 0:
            kwargs["start_from_id"] = start_from_id

        call_command("autodb_clone_sync", **kwargs)
