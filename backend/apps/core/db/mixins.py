import uuid

from django.db import models
from django.utils import timezone


class UUIDPrimaryKeyMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublishableMixin(models.Model):
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def publish(self) -> None:
        self.is_active = True
        self.published_at = timezone.now()


class SortableMixin(models.Model):
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ("sort_order", "id")
