from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supplier_imports", "0009_alter_supplierrawoffer_category_mapping_reason"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="importrowerror",
            index=models.Index(fields=["-created_at"], name="supplier_row_error_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="supplierrawoffer",
            index=models.Index(fields=["is_valid"], name="supplier_raw_offer_valid_idx"),
        ),
        migrations.AddIndex(
            model_name="supplierrawoffer",
            index=models.Index(
                fields=["match_status", "is_valid"],
                name="supplier_raw_match_valid_idx",
            ),
        ),
    ]
