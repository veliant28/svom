from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin


class UserManager(DjangoUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email)

        legacy_username = extra_fields.pop("username", None)
        if legacy_username and not extra_fields.get("first_name"):
            extra_fields["first_name"] = str(legacy_username).strip()

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(TimestampedMixin, AbstractUser):
    username = None
    LANGUAGE_UK = "uk"
    LANGUAGE_RU = "ru"
    LANGUAGE_EN = "en"

    LANGUAGE_CHOICES = (
        (LANGUAGE_UK, _("Украинский")),
        (LANGUAGE_RU, _("Русский")),
        (LANGUAGE_EN, _("Английский")),
    )

    email = models.EmailField(_("Email"), unique=True)
    middle_name = models.CharField(_("Отчество"), max_length=150, blank=True)
    phone = models.CharField(_("Телефон"), max_length=32, blank=True)
    preferred_language = models.CharField(
        _("Предпочитаемый язык"),
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default=LANGUAGE_UK,
    )

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ("-date_joined",)
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self._assign_default_system_role_if_missing()

    def _assign_default_system_role_if_missing(self) -> None:
        if self.is_superuser:
            return
        if self.groups.exists():
            return
        from apps.users.rbac import set_user_system_role

        set_user_system_role(user=self, role_code="user")

    def __str__(self) -> str:
        return self.get_full_name() or self.email
