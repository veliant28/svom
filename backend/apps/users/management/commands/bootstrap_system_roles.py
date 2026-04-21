from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.users.rbac import ensure_system_groups_exist


class Command(BaseCommand):
    help = "Ensure built-in backoffice system roles and capability permissions exist."

    def handle(self, *args, **options):
        groups = ensure_system_groups_exist()
        self.stdout.write(self.style.SUCCESS(f"System role groups ensured: {', '.join(sorted(groups.keys()))}"))
