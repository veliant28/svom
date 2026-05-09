from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.services.taxonomy_v2 import TAXONOMY_ROOT_SPECS, TO_COLLECTION_SPEC, TaxonomyV2Seeder


class Command(BaseCommand):
    help = "Seed SVOM catalog taxonomy v2 and header navigation collections."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing.")
        parser.add_argument(
            "--prune-old",
            action="store_true",
            help="Reserved for explicit old taxonomy cleanup. Current implementation never prunes implicitly.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        if options.get("prune_old"):
            self.stdout.write(self.style.WARNING("prune_old_requested=True but no destructive pruning is implemented."))

        stats = TaxonomyV2Seeder(dry_run=dry_run).seed()

        self.stdout.write(f"dry_run={dry_run}")
        self.stdout.write(f"roots_expected={len(TAXONOMY_ROOT_SPECS)}")
        self.stdout.write(f"navigation_collection={TO_COLLECTION_SPEC.slug}")
        for key, value in stats.as_dict().items():
            self.stdout.write(f"{key}: {value}")
