from django.db import migrations
from django.db.models import F


def backfill_last_seen_at(apps, schema_editor):
    SupplierOffer = apps.get_model("pricing", "SupplierOffer")
    SupplierOffer.objects.filter(last_seen_at__isnull=True).update(last_seen_at=F("updated_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0006_supplieroffer_last_seen_at"),
    ]

    operations = [
        migrations.RunPython(backfill_last_seen_at, migrations.RunPython.noop),
    ]
