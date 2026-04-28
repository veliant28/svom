from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0008_supplieroffer_price_levels"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "UPDATE pricing_supplieroffer "
                "SET price_levels = '[]'::jsonb "
                "WHERE price_levels IS NULL;"
                "ALTER TABLE pricing_supplieroffer "
                "ALTER COLUMN price_levels SET DEFAULT '[]'::jsonb;"
            ),
            reverse_sql=(
                "ALTER TABLE pricing_supplieroffer "
                "ALTER COLUMN price_levels DROP DEFAULT;"
            ),
        ),
    ]
