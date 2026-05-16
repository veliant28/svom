from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.catalog.models import AutoDbProductLinkQuality, Product


@receiver(post_save, sender=Product)
def ensure_link_quality_for_autodb_link(sender, instance: Product, **kwargs) -> None:  # noqa: ARG001
    article_key = str(getattr(instance, "autodb_article_key", "") or "").strip()
    supplier_id = getattr(instance, "autodb_supplier_id", None)
    article_number = str(getattr(instance, "autodb_article_number", "") or "").strip()
    if not article_key or not supplier_id or not article_number:
        return

    if AutoDbProductLinkQuality.objects.filter(product=instance, autodb_article_key=article_key).exists():
        return

    AutoDbProductLinkQuality.objects.create(
        product=instance,
        autodb_article_key=article_key,
        autodb_supplier_id=int(supplier_id),
        autodb_article_number=article_number,
        status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        reason="autodb_link_saved_without_quality_record",
        evidence={
            "source": "catalog.signals.ensure_link_quality_for_autodb_link",
            "product_id": str(instance.id),
        },
        checked_at=timezone.now(),
        manually_confirmed=False,
        note="auto-created on product save",
    )
