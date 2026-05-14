from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("compatibility", "0005_prepare_vehicles_retirement"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="productfitment",
            name="compatibility_fitment_unique_product_modification",
        ),
        migrations.RemoveField(
            model_name="productfitment",
            name="modification",
        ),
    ]
