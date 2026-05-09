from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Product
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.pricing.services import ProductRepricer
from apps.pricing.services.calculator import PricingCalculator
from apps.pricing.services.offer_selector import OfferSelector
from apps.pricing.services.policy_resolver import PolicyResolver


@dataclass
class RepriceSupplierSummary:
    products_scoped: int = 0
    supplier_offers_found: int = 0
    would_create_product_price: int = 0
    would_update_product_price: int = 0
    repriced: int = 0
    skipped_no_offer: int = 0
    skipped_invalid_price: int = 0
    skipped_markup_guard: int = 0
    skipped_locked: int = 0
    errors: int = 0
    unchanged: int = 0


class Command(BaseCommand):
    help = "Reprice products for a supplier using standard pricing services."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. gpl")
        parser.add_argument("--limit", type=int, default=0, help="Limit products")
        parser.add_argument("--dry-run", action="store_true", help="Preview repricing without writes")
        parser.add_argument("--apply", action="store_true", help="Apply repricing writes")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        dry_run = bool(options.get("dry_run"))
        do_apply = bool(options.get("apply"))
        if dry_run == do_apply:
            raise CommandError("Specify exactly one mode: --dry-run or --apply.")
        limit = max(int(options.get("limit") or 0), 0)

        products_qs = (
            Product.objects.filter(supplier_offers__supplier__code=supplier_code)
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            products_qs = products_qs[:limit]
        products = list(products_qs)
        product_ids = [str(item.id) for item in products]

        summary = RepriceSupplierSummary(products_scoped=len(products))
        offer_counts = (
            SupplierOffer.objects.filter(supplier__code=supplier_code, product_id__in=product_ids)
            .values("product_id")
            .count()
        )
        summary.supplier_offers_found = int(offer_counts)

        selector = OfferSelector()
        resolver = PolicyResolver()
        calculator = PricingCalculator()
        repricer = ProductRepricer()

        policy_usage: dict[str, int] = {}
        price_samples: list[str] = []
        min_price: Decimal | None = None
        max_price: Decimal | None = None

        for product in products:
            existing_price = ProductPrice.objects.filter(product=product).first()
            best_offer = selector.select_best_offer(product)
            if best_offer is None:
                summary.skipped_no_offer += 1
                continue
            if Decimal(best_offer.purchase_price or 0) <= 0:
                summary.skipped_invalid_price += 1
                continue

            policy = resolver.resolve_policy(product=product, offer=best_offer)
            calc = calculator.calculate(offer=best_offer, policy=policy)
            final_price = Decimal(calc.final_price or 0)
            purchase_price = Decimal(calc.purchase_price or 0)
            policy_key = str(getattr(policy, "name", "") or "no_policy")
            policy_usage[policy_key] = policy_usage.get(policy_key, 0) + 1

            min_price = final_price if min_price is None else min(min_price, final_price)
            max_price = final_price if max_price is None else max(max_price, final_price)
            if len(price_samples) < 10:
                price_samples.append(f"{product.id}:{final_price}")

            if final_price <= 0:
                summary.skipped_invalid_price += 1
                continue
            if final_price <= purchase_price:
                summary.skipped_markup_guard += 1
                continue

            if existing_price is None:
                summary.would_create_product_price += 1
            else:
                summary.would_update_product_price += 1
                if (
                    Decimal(existing_price.final_price or 0) == final_price
                    and Decimal(existing_price.purchase_price or 0) == purchase_price
                    and str(getattr(existing_price.policy, "id", "") or "") == str(getattr(policy, "id", "") or "")
                ):
                    summary.unchanged += 1

            if do_apply:
                if existing_price and bool(existing_price.auto_calculation_locked):
                    summary.skipped_locked += 1
                    continue
                try:
                    result = repricer.recalculate_product(
                        product=product,
                        trigger_note=f"cli:reprice_supplier_products:{supplier_code}",
                    )
                except Exception:
                    summary.errors += 1
                    continue

                if result.status == "repriced":
                    summary.repriced += 1
                elif result.reason == "locked":
                    summary.skipped_locked += 1
                elif result.reason == "no_offer":
                    summary.skipped_no_offer += 1

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(f"reprice_supplier_products {mode} summary:")
        self.stdout.write(f"- supplier: {supplier_code}")
        self.stdout.write(f"- products_scoped: {summary.products_scoped}")
        self.stdout.write(f"- supplier_offers_found: {summary.supplier_offers_found}")
        self.stdout.write(f"- would_create ProductPrice: {summary.would_create_product_price}")
        self.stdout.write(f"- would_update ProductPrice: {summary.would_update_product_price}")
        self.stdout.write(f"- repriced: {summary.repriced}")
        self.stdout.write(f"- skipped_no_offer: {summary.skipped_no_offer}")
        self.stdout.write(f"- skipped_invalid_price: {summary.skipped_invalid_price}")
        self.stdout.write(f"- skipped_markup_guard: {summary.skipped_markup_guard}")
        self.stdout.write(f"- skipped_locked: {summary.skipped_locked}")
        self.stdout.write(f"- unchanged: {summary.unchanged}")
        self.stdout.write(f"- errors: {summary.errors}")
        self.stdout.write(f"- price_min: {min_price if min_price is not None else 'n/a'}")
        self.stdout.write(f"- price_max: {max_price if max_price is not None else 'n/a'}")
        self.stdout.write(f"- price_samples: {', '.join(price_samples) if price_samples else 'n/a'}")
        self.stdout.write("- markup_rule_used (top):")
        for name, count in sorted(policy_usage.items(), key=lambda item: (-item[1], item[0]))[:10]:
            self.stdout.write(f"  - {name}: {count}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- SupplierOffer source values unchanged=1")
