from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.autodb.services.product_linker import AutoDbProductLinkService


class Command(BaseCommand):
    help = "Link one Product to Auto_DB_Pro article/supplier by product article+brand."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, help="Product UUID")
        parser.add_argument("--dry-run", action="store_true", help="Do not save Product changes")
        parser.add_argument("--no-remote", action="store_true", help="Disable remote Auto_DB_Pro fallback")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        if not product_id:
            raise CommandError("--product-id is required")

        dry_run = bool(options.get("dry_run"))
        allow_remote = not bool(options.get("no_remote"))
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )
        try:
            AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=allow_remote)
        except AutoDbRemoteConfigError as exc:
            raise CommandError(str(exc)) from exc

        service = AutoDbProductLinkService()
        try:
            result = service.link_product_by_id(product_id=product_id, dry_run=dry_run, allow_remote=allow_remote)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        self.stdout.write("Auto_DB_Pro product link:")
        self.stdout.write(f"- dry_run: {dry_run}")
        self.stdout.write(f"- allow_remote: {allow_remote}")
        self.stdout.write(f"- wait_for_autodb: {wait_for_autodb}")
        self.stdout.write(f"- product_id: {result.product_id}")
        self.stdout.write(f"- linked: {result.linked}")
        self.stdout.write(f"- link_status: {result.link_status}")
        self.stdout.write(f"- autodb_supplier_id: {result.supplier_id or '-'}")
        self.stdout.write(f"- autodb_article_id: {result.article_id or '-'}")
        self.stdout.write(f"- autodb_article_number: {result.article_number or '-'}")
        self.stdout.write(f"- autodb_article_key: {result.article_key or '-'}")
        self.stdout.write(f"- normalized_brand: {result.normalized_brand}")
        self.stdout.write(f"- normalized_article: {result.normalized_article}")
        if result.warnings:
            self.stdout.write("- warnings:")
            for warning in result.warnings:
                self.stdout.write(f"  - {warning}")
