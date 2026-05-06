from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("autodb", "0006_sync_state_field_alignment"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoDbSupplierBrandAlias",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("raw_brand", models.CharField(max_length=255, verbose_name="Raw brand")),
                ("normalized_raw_brand", models.CharField(db_index=True, max_length=255, verbose_name="Normalized raw brand")),
                ("autodb_supplier_name", models.CharField(blank=True, default="", max_length=255, verbose_name="Auto_DB_Pro supplier name")),
                ("source", models.CharField(choices=[("auto", "auto"), ("manual", "manual"), ("imported", "imported")], default="auto", max_length=32, verbose_name="Source")),
                ("confidence", models.DecimalField(decimal_places=2, default=0.0, max_digits=5, verbose_name="Confidence")),
                ("manual_confirmed", models.BooleanField(db_index=True, default=False, verbose_name="Manual confirmed")),
                ("note", models.TextField(blank=True, default="", verbose_name="Note")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Active")),
                ("autodb_supplier_id", models.BigIntegerField(db_index=True, verbose_name="Auto_DB_Pro supplier ID")),
            ],
            options={
                "verbose_name": "Auto_DB supplier brand alias",
                "verbose_name_plural": "Auto_DB supplier brand aliases",
                "db_table": "autodb_supplier_brand_aliases",
            },
        ),
        migrations.AddIndex(
            model_name="autodbsupplierbrandalias",
            index=models.Index(fields=["normalized_raw_brand", "is_active"], name="autodb_alias_norm_active_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbsupplierbrandalias",
            index=models.Index(fields=["autodb_supplier_id", "is_active"], name="autodb_alias_sup_active_idx"),
        ),
        migrations.AddIndex(
            model_name="autodbsupplierbrandalias",
            index=models.Index(fields=["manual_confirmed", "is_active"], name="autodb_alias_manual_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="autodbsupplierbrandalias",
            constraint=models.UniqueConstraint(fields=("normalized_raw_brand",), name="autodb_alias_norm_unique"),
        ),
    ]
