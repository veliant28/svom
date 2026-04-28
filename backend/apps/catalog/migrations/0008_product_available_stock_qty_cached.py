from django.db import migrations, models
from django.db.models import IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce


def backfill_available_stock_qty_cached(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    SupplierOffer = apps.get_model("pricing", "SupplierOffer")

    available_sum = (
        SupplierOffer.objects.filter(
            product_id=OuterRef("pk"),
            is_available=True,
            stock_qty__gt=0,
        )
        .values("product_id")
        .annotate(total=Sum("stock_qty"))
        .values("total")[:1]
    )

    Product.objects.update(
        available_stock_qty_cached=Coalesce(
            Subquery(available_sum, output_field=IntegerField()),
            Value(0),
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_product_category_manually_locked"),
        ("pricing", "0009_supplieroffer_price_levels_db_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="available_stock_qty_cached",
            field=models.IntegerField(db_index=True, default=0, verbose_name="Кэш доступного остатка"),
        ),
        migrations.RunPython(backfill_available_stock_qty_cached, migrations.RunPython.noop),
    ]
