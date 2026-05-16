from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0025_product_views_count"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS catalog_product_name_idx ON catalog_product (name);",
                    reverse_sql="DROP INDEX IF EXISTS catalog_product_name_idx;",
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="product",
                    index=models.Index(fields=("name",), name="catalog_product_name_idx"),
                ),
            ],
        ),
    ]
