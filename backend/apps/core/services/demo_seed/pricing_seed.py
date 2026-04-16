from __future__ import annotations

from decimal import Decimal

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory, PricingPolicy, PricingRule, ProductPrice, Supplier, SupplierOffer
from apps.pricing.services import ProductRepricer


def seed_pricing_demo(*, products: list[Product]) -> dict[str, int]:
    suppliers = _seed_suppliers()
    offers_count = _seed_supplier_offers(products=products, suppliers=suppliers)
    policies_count = _seed_pricing_policies(suppliers=suppliers)

    repricing_stats = ProductRepricer().recalculate_products(
        Product.objects.filter(id__in=[product.id for product in products]).select_related("brand", "category"),
        source=PriceHistory.SOURCE_AUTO,
        trigger_note="seed_demo_data",
    )

    return {
        "suppliers": len(suppliers),
        "supplier_offers": offers_count,
        "pricing_policies": policies_count,
        "product_prices": ProductPrice.objects.filter(product_id__in=[product.id for product in products]).count(),
        "repriced": repricing_stats.get("repriced", 0),
        "repriced_skipped": repricing_stats.get("skipped", 0),
        "repriced_errors": repricing_stats.get("errors", 0),
    }


def _seed_suppliers() -> list[Supplier]:
    payload = [
        {"code": "alpha-parts", "name": "Alpha Parts Supply"},
        {"code": "euro-auto-trade", "name": "Euro Auto Trade"},
    ]

    result: list[Supplier] = []
    for item in payload:
        supplier, _ = Supplier.objects.update_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "contact_email": f"{item['code']}@demo.local",
                "is_active": True,
            },
        )
        result.append(supplier)

    return result


def _seed_supplier_offers(*, products: list[Product], suppliers: list[Supplier]) -> int:
    count = 0
    base_prices = {
        "BOS-F026407123": Decimal("145.00"),
        "MAN-W71295": Decimal("172.00"),
        "CAS-EDGE-5W30-4L": Decimal("1140.00"),
        "OSR-H7-64210": Decimal("165.00"),
        "BOS-AIR-S1988": Decimal("390.00"),
        "CAS-MAGN-5W40-4L": Decimal("1220.00"),
    }

    for index, product in enumerate(products, start=1):
        for supplier_index, supplier in enumerate(suppliers, start=1):
            base_price = base_prices.get(product.sku, Decimal("200.00") + Decimal(str(index * 15)))
            purchase_price = base_price + Decimal(str((supplier_index - 1) * 8))
            logistics_cost = Decimal("22.00") + Decimal(str(index))
            extra_cost = Decimal("5.00")

            SupplierOffer.objects.update_or_create(
                supplier=supplier,
                product=product,
                supplier_sku=f"{supplier.code.upper()}-{product.sku}",
                defaults={
                    "currency": "UAH",
                    "purchase_price": purchase_price,
                    "logistics_cost": logistics_cost,
                    "extra_cost": extra_cost,
                    "stock_qty": 10 + (index * supplier_index),
                    "lead_time_days": supplier_index,
                    "is_available": True,
                },
            )
            count += 1

    return count


def _seed_pricing_policies(*, suppliers: list[Supplier]) -> int:
    global_policy, _ = PricingPolicy.objects.update_or_create(
        name="Global demo policy",
        defaults={
            "scope": PricingPolicy.SCOPE_GLOBAL,
            "priority": 500,
            "percent_markup": Decimal("24.00"),
            "fixed_markup": Decimal("0.00"),
            "min_margin_percent": Decimal("10.00"),
            "min_price": Decimal("50.00"),
            "rounding_step": Decimal("1.00"),
            "psychological_rounding": True,
            "lock_auto_recalc": False,
            "is_active": True,
            "supplier": None,
            "brand": None,
            "category": None,
        },
    )

    supplier_policy, _ = PricingPolicy.objects.update_or_create(
        name="Supplier demo policy",
        defaults={
            "scope": PricingPolicy.SCOPE_SUPPLIER,
            "priority": 300,
            "supplier": suppliers[0],
            "percent_markup": Decimal("20.00"),
            "fixed_markup": Decimal("12.00"),
            "min_margin_percent": Decimal("8.00"),
            "min_price": Decimal("40.00"),
            "rounding_step": Decimal("1.00"),
            "psychological_rounding": False,
            "lock_auto_recalc": False,
            "is_active": True,
            "brand": None,
            "category": None,
        },
    )

    _seed_policy_rules(global_policy)
    _seed_policy_rules(supplier_policy)

    return 2


def _seed_policy_rules(policy: PricingPolicy) -> None:
    PricingRule.objects.update_or_create(
        policy=policy,
        priority=100,
        cost_from=Decimal("0.00"),
        cost_to=Decimal("500.00"),
        defaults={
            "percent_markup": Decimal("30.00"),
            "fixed_markup": Decimal("8.00"),
        },
    )

    PricingRule.objects.update_or_create(
        policy=policy,
        priority=200,
        cost_from=Decimal("500.01"),
        cost_to=None,
        defaults={
            "percent_markup": Decimal("18.00"),
            "fixed_markup": Decimal("15.00"),
        },
    )
