from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbArticleImage(models.Model):
    supplier = models.ForeignKey(
        "autodb.AutoDbSupplier",
        on_delete=models.CASCADE,
        related_name="article_images",
    )
    article_number = models.CharField(_("Артикул"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)
    image_url = models.TextField(_("URL изображения"), blank=True, default="")
    image_path = models.TextField(_("Путь изображения"), blank=True, default="")
    file_extension = models.CharField(_("Расширение файла"), max_length=16, blank=True, default="")
    is_primary = models.BooleanField(_("Основное изображение"), default=False)
    sort_order = models.IntegerField(_("Порядок сортировки"), default=0)

    class Meta:
        db_table = "autodb_article_images"
        verbose_name = _("Изображение артикула Auto-DB")
        verbose_name_plural = _("Изображения артикулов Auto-DB")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "article_number", "image_url", "image_path"),
                name="adb_img_uq_sup_art_url_path",
            )
        ]
        indexes = [
            models.Index(fields=("supplier", "normalized_article"), name="adb_img_sup_norm_art_idx"),
            models.Index(fields=("is_primary",), name="adb_img_primary_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}:{self.article_number}:{self.image_url or self.image_path}"

