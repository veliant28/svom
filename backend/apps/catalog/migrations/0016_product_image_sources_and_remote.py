from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0015_attribute_source_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productimage",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="catalog/products/images/", verbose_name="Изображение"),
        ),
        migrations.AddField(
            model_name="productimage",
            name="remote_url",
            field=models.URLField(blank=True, default="", max_length=1000, verbose_name="Remote URL"),
        ),
        migrations.AddField(
            model_name="productimage",
            name="source",
            field=models.CharField(
                blank=True,
                choices=[("manual", "Manual"), ("gpl_price", "GPL price"), ("autodb_pro", "Auto_DB_Pro"), ("imported", "Imported")],
                db_index=True,
                default="imported",
                max_length=24,
                verbose_name="Источник",
            ),
        ),
        migrations.AddField(
            model_name="productimage",
            name="source_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="Source hash"),
        ),
        migrations.AddField(
            model_name="productimage",
            name="source_payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="Source payload"),
        ),
        migrations.AddField(
            model_name="productimage",
            name="is_stale",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Устаревшее изображение"),
        ),
        migrations.AddField(
            model_name="productimage",
            name="stale_reason",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="Причина устаревания"),
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                condition=~Q(remote_url=""),
                fields=("product", "source", "remote_url"),
                name="catalog_productimage_unique_remote_per_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                condition=~Q(source_hash=""),
                fields=("product", "source", "source_hash"),
                name="catalog_productimage_unique_source_hash_per_source",
            ),
        ),
    ]
