from django.db import migrations, models


def backfill_product_brand_fields(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    db_alias = schema_editor.connection.alias
    for product in Product.objects.using(db_alias).only("id", "brand_source").iterator(chunk_size=2000):
        update_fields: list[str] = []
        if not str(product.brand_source or "").strip():
            product.brand_source = "unknown"
            update_fields.append("brand_source")
        if update_fields:
            update_fields.append("updated_at")
            product.save(update_fields=tuple(update_fields), using=db_alias)


def rollback_noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0020_category_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="autodb_supplier_name",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255, verbose_name="Auto_DB_Pro supplier name"),
        ),
        migrations.AddField(
            model_name="product",
            name="display_brand_name",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255, verbose_name="Отображаемый бренд"),
        ),
        migrations.AddField(
            model_name="product",
            name="brand_source",
            field=models.CharField(
                blank=True,
                choices=[("autodb_pro", "Auto_DB_Pro"), ("manual", "Manual"), ("supplier_fallback", "Supplier fallback"), ("unknown", "Unknown")],
                db_index=True,
                default="",
                max_length=32,
                verbose_name="Источник бренда",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="brand_source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Хеш источника бренда"),
        ),
        migrations.AddField(
            model_name="product",
            name="brand_manually_locked",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Бренд закреплен вручную"),
        ),
        migrations.RunPython(backfill_product_brand_fields, rollback_noop),
    ]
