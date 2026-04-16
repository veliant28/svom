from django.core.management.base import BaseCommand

from apps.search.services import ProductIndexer


class Command(BaseCommand):
    help = "Reindex product documents in Elasticsearch using the configured search backend."

    def add_arguments(self, parser):
        parser.add_argument(
            "--product-id",
            action="append",
            dest="product_ids",
            default=None,
            help="Product UUID to reindex. Can be passed multiple times.",
        )

    def handle(self, *args, **options):
        product_ids = options.get("product_ids")
        stats = ProductIndexer().reindex_products(product_ids=product_ids)

        self.stdout.write("Reindex finished:")
        for key, value in stats.items():
            self.stdout.write(f"  - {key}: {value}")
