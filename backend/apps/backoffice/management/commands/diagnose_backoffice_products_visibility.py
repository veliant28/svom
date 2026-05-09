from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.catalog.models import Product


@dataclass
class StepCount:
    key: str
    count: int


class Command(BaseCommand):
    help = "Diagnose why backoffice products visibility differs from dashboard totals."

    def handle(self, *args, **options):
        base_qs = Product.objects.all()
        total = base_qs.count()

        dashboard_published = Product.objects.filter(is_active=True).count()

        steps: list[StepCount] = [
            StepCount("base", total),
            StepCount("active", Product.objects.filter(is_active=True).count()),
            StepCount("with_category", Product.objects.filter(category__isnull=False).count()),
            StepCount("without_category", Product.objects.filter(category__isnull=True).count()),
            StepCount("with_autodb_link", Product.objects.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="").count()),
            StepCount("missing_autodb_link", Product.objects.filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_number="")).count()),
            StepCount("with_display_brand", Product.objects.exclude(display_brand_name="").count()),
            StepCount("with_supplier_offers", Product.objects.filter(supplier_offers__isnull=False).distinct().count()),
        ]

        admin_queryset = Product.objects.select_related("brand", "category", "product_price", "product_price__policy").order_by("name")
        admin_queryset_count = admin_queryset.count()
        admin_queryset_page_len = len(list(admin_queryset.values_list("id", flat=True)[:25]))

        self.stdout.write("Backoffice products visibility diagnostics")
        self.stdout.write(f"- products_total: {total}")
        self.stdout.write(f"- products_dashboard_published: {dashboard_published}")
        self.stdout.write(f"- products_admin_queryset_count: {admin_queryset_count}")
        self.stdout.write(f"- products_admin_queryset_first_page_len: {admin_queryset_page_len}")

        self.stdout.write("- products_after_each_filter:")
        for step in steps:
            self.stdout.write(f"  - {step.key}: {step.count}")

        sample_visible = list(admin_queryset.values("id", "name", "slug", "is_active")[:10])
        sample_hidden_category = list(
            Product.objects.filter(category__isnull=True).values("id", "name", "slug", "is_active")[:10]
        )

        self.stdout.write("- sample_visible_products:")
        for row in sample_visible:
            self.stdout.write(f"  - {row['id']} | {row['name']} | {row['slug']} | active={row['is_active']}")

        self.stdout.write("- sample_hidden_products(category_is_null):")
        for row in sample_hidden_category:
            self.stdout.write(f"  - {row['id']} | {row['name']} | {row['slug']} | active={row['is_active']}")

        self.stdout.write("- first_excluded_reason_counts:")
        self.stdout.write("  - category_is_null: " + str(Product.objects.filter(category__isnull=True).count()))
        self.stdout.write("  - inactive: " + str(Product.objects.filter(is_active=False).count()))
        self.stdout.write("  - no_supplier_offer: " + str(Product.objects.exclude(id__in=Product.objects.filter(supplier_offers__isnull=False).values("id")).count()))
