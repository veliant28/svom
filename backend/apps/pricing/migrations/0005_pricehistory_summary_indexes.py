from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0004_alter_currencyrate_options_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="pricehistory",
            index=models.Index(
                fields=["source", "created_at", "product"],
                name="pricing_ph_src_cr_prod_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pricehistory",
            index=models.Index(
                fields=["source", "product"],
                name="pricing_ph_src_prod_idx",
            ),
        ),
    ]
