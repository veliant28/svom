from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.catalog.models import Product
from apps.compatibility.models import ProductFitment
from apps.users.models import GarageVehicle
from apps.vehicles.models import (
    VehicleEngine,
    VehicleGeneration,
    VehicleMake,
    VehicleModel,
    VehicleModification,
)

User = get_user_model()


def seed_vehicles_demo(*, products: list[Product]) -> dict[str, int]:
    hierarchy = _seed_vehicle_hierarchy()
    demo_user = _seed_demo_user()
    garage_count = _seed_garage(demo_user, hierarchy)
    fitment_count = _seed_fitments(products=products, modifications=hierarchy["modifications"])

    return {
        "vehicle_makes": len(hierarchy["makes"]),
        "vehicle_models": len(hierarchy["models"]),
        "vehicle_generations": len(hierarchy["generations"]),
        "vehicle_engines": len(hierarchy["engines"]),
        "vehicle_modifications": len(hierarchy["modifications"]),
        "garage_vehicles": garage_count,
        "product_fitments": fitment_count,
    }


def _seed_vehicle_hierarchy() -> dict[str, list]:
    toyota, _ = VehicleMake.objects.update_or_create(
        slug="toyota",
        defaults={"name": "Toyota", "is_active": True},
    )
    bmw, _ = VehicleMake.objects.update_or_create(
        slug="bmw",
        defaults={"name": "BMW", "is_active": True},
    )

    camry, _ = VehicleModel.objects.update_or_create(
        make=toyota,
        slug="camry",
        defaults={"name": "Camry", "is_active": True},
    )
    series3, _ = VehicleModel.objects.update_or_create(
        make=bmw,
        slug="3-series",
        defaults={"name": "3 Series", "is_active": True},
    )

    camry_xv70, _ = VehicleGeneration.objects.update_or_create(
        model=camry,
        name="XV70",
        year_start=2017,
        defaults={"year_end": None, "is_active": True},
    )
    bmw_g20, _ = VehicleGeneration.objects.update_or_create(
        model=series3,
        name="G20",
        year_start=2018,
        defaults={"year_end": None, "is_active": True},
    )

    camry_engine, _ = VehicleEngine.objects.update_or_create(
        generation=camry_xv70,
        name="2.5 Hybrid",
        code="A25A-FXS",
        defaults={
            "fuel_type": VehicleEngine.FUEL_HYBRID,
            "displacement_cc": 2487,
            "power_hp": 218,
            "is_active": True,
        },
    )
    bmw_engine, _ = VehicleEngine.objects.update_or_create(
        generation=bmw_g20,
        name="330i 2.0 Turbo",
        code="B48B20",
        defaults={
            "fuel_type": VehicleEngine.FUEL_PETROL,
            "displacement_cc": 1998,
            "power_hp": 258,
            "is_active": True,
        },
    )

    camry_mod, _ = VehicleModification.objects.update_or_create(
        engine=camry_engine,
        name="Sedan e-CVT FWD",
        year_start=2019,
        defaults={
            "year_end": None,
            "body_type": "Sedan",
            "transmission": "e-CVT",
            "drivetrain": "FWD",
            "is_active": True,
        },
    )
    bmw_mod, _ = VehicleModification.objects.update_or_create(
        engine=bmw_engine,
        name="Sedan AT RWD",
        year_start=2019,
        defaults={
            "year_end": None,
            "body_type": "Sedan",
            "transmission": "AT",
            "drivetrain": "RWD",
            "is_active": True,
        },
    )

    return {
        "makes": [toyota, bmw],
        "models": [camry, series3],
        "generations": [camry_xv70, bmw_g20],
        "engines": [camry_engine, bmw_engine],
        "modifications": [camry_mod, bmw_mod],
    }


def _seed_demo_user() -> User:
    demo_user, created = User.objects.get_or_create(
        email="demo@svom.local",
        defaults={
            "first_name": "Demo",
            "last_name": "Driver",
            "is_active": True,
        },
    )
    if created:
        demo_user.set_password("demo12345")
        demo_user.save(update_fields=("password",))
    return demo_user


def _seed_garage(demo_user: User, hierarchy: dict[str, list]) -> int:
    camry_mod = hierarchy["modifications"][0]
    bmw_mod = hierarchy["modifications"][1]

    garage_payload = [
        {
            "modification": camry_mod,
            "vin": "JTNB11HKXK3000001",
            "nickname": "Family Camry",
            "year": 2020,
            "is_primary": True,
        },
        {
            "modification": bmw_mod,
            "vin": "WBA5R5C53LFH00001",
            "nickname": "Weekend BMW",
            "year": 2021,
            "is_primary": False,
        },
    ]

    count = 0
    for item in garage_payload:
        modification = item["modification"]
        GarageVehicle.objects.update_or_create(
            user=demo_user,
            make=modification.engine.generation.model.make,
            model=modification.engine.generation.model,
            generation=modification.engine.generation,
            engine=modification.engine,
            modification=modification,
            vin=item["vin"],
            defaults={
                "nickname": item["nickname"],
                "year": item["year"],
                "is_primary": item["is_primary"],
            },
        )
        count += 1

    return count


def _seed_fitments(*, products: list[Product], modifications: list[VehicleModification]) -> int:
    if not products:
        return 0

    camry_mod = modifications[0]
    bmw_mod = modifications[1]

    products_by_sku = {product.sku: product for product in products}
    fitment_plan = {
        # Fits Toyota Camry only.
        "BOS-F026407123": [camry_mod],
        # Fits BMW only.
        "MAN-W71295": [bmw_mod],
        # Fits both.
        "CAS-EDGE-5W30-4L": [camry_mod, bmw_mod],
        # Compatibility unknown.
        "OSR-H7-64210": [],
        # Fits Toyota Camry only.
        "BOS-AIR-S1988": [camry_mod],
        # Compatibility unknown.
        "CAS-MAGN-5W40-4L": [],
    }

    ProductFitment.objects.filter(product_id__in=[product.id for product in products]).delete()

    count = 0
    for sku, target_modifications in fitment_plan.items():
        product = products_by_sku.get(sku)
        if product is None:
            continue

        for modification in target_modifications:
            ProductFitment.objects.create(
                product=product,
                modification=modification,
                note="Seeded demo fitment",
                is_exact=True,
            )
            count += 1

    return count
