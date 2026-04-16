from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.services.demo_seed import (
    seed_catalog_demo,
    seed_commerce_demo,
    seed_marketing_demo,
    seed_pricing_demo,
    seed_vehicles_demo,
)


class Command(BaseCommand):
    help = "Seed demo catalog, marketing and pricing data for usable local demo state."

    @transaction.atomic
    def handle(self, *args, **options):
        catalog_data = seed_catalog_demo()
        marketing_stats = seed_marketing_demo()
        vehicles_stats = seed_vehicles_demo(products=catalog_data.products)
        pricing_stats = seed_pricing_demo(products=catalog_data.products)
        commerce_stats = seed_commerce_demo(products=catalog_data.products)

        self.stdout.write(self.style.SUCCESS("Demo seed completed."))
        self.stdout.write("Catalog:")
        for key, value in catalog_data.stats.items():
            self.stdout.write(f"  - {key}: {value}")

        self.stdout.write("Marketing:")
        for key, value in marketing_stats.items():
            self.stdout.write(f"  - {key}: {value}")

        self.stdout.write("Vehicles/Garage:")
        for key, value in vehicles_stats.items():
            self.stdout.write(f"  - {key}: {value}")

        self.stdout.write("Pricing:")
        for key, value in pricing_stats.items():
            self.stdout.write(f"  - {key}: {value}")

        self.stdout.write("Commerce:")
        for key, value in commerce_stats.items():
            self.stdout.write(f"  - {key}: {value}")
