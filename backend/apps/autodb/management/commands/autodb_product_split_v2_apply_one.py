from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.matching.product_split_v2_apply_one import AutoDbProductSplitV2ApplyOneService


class Command(BaseCommand):
    help = "Apply one approved clean split v2 candidate and export full verification package."

    def handle(self, *args, **options):
        payload = AutoDbProductSplitV2ApplyOneService().run()
        apply_result = payload.get("apply_result")
        self.stdout.write("Done")
        self.stdout.write(f"source_product_id={getattr(apply_result, 'source_product_id', '')}")
        self.stdout.write(f"new_product_id={getattr(apply_result, 'new_product_id', '')}")
        self.stdout.write(f"new_product_sku={getattr(apply_result, 'new_product_sku', '')}")
        self.stdout.write(f"new_product_svom_sku={getattr(apply_result, 'new_product_svom_sku', '')}")

