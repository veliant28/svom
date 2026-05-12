from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.deterministic_brand_binding import AutoDbDeterministicBrandBindingService


class Command(BaseCommand):
    help = "Apply deterministic diacritics/trademark Auto_DB brand binding (brand-level only)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False)

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        service = AutoDbDeterministicBrandBindingService()
        payload = service.run(apply_changes=apply_changes)
        paths = service.write_exports(payload)

        for key, path in sorted(paths.items()):
            self.stdout.write(f"{key}: {path}")
