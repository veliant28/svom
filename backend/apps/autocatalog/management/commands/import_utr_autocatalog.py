from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from apps.autocatalog.application.utr_import_command import CommandOutput, run_utr_import_command


class Command(BaseCommand):
    help = _("Импортирует автокаталог из UTR applicability по detail_id из Product и/или UTR article.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=_("Ограничить количество utr_detail_id для обработки."),
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help=_("Смещение по списку utr_detail_id для батчевого запуска."),
        )
        parser.add_argument(
            "--resolve-utr-articles",
            action="store_true",
            help=_("Сначала получить detail_id через UTR search по артикулу UTR из сырых офферов."),
        )
        parser.add_argument(
            "--resolve-limit",
            type=int,
            default=None,
            help=_("Ограничить количество пар артикул+бренд для резолва detail_id."),
        )
        parser.add_argument(
            "--resolve-offset",
            type=int,
            default=0,
            help=_("Смещение по парам артикул+бренд для резолва detail_id."),
        )
        parser.add_argument(
            "--resolve-until-empty",
            action="store_true",
            help=_("Крутить резолв батчами до исчерпания кандидатов."),
        )
        parser.add_argument(
            "--retry-unresolved",
            action="store_true",
            help=_("Резолвить пары, у которых уже есть mapping c пустым utr_detail_id."),
        )
        parser.add_argument(
            "--resolve-only",
            action="store_true",
            help=_("Выполнить только резолв article->detail, без импорта applicability."),
        )
        parser.add_argument(
            "--products-only",
            action="store_true",
            help=_("Брать detail_id только из Product.utr_detail_id, без резолва по артикулам."),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help=_("Размер батча detail_id за один внутренний проход."),
        )
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help=_("Игнорировать кеш и существующие mapping-и, принудительно дергать UTR."),
        )

    def handle(self, *args, **options):
        run_utr_import_command(
            raw_options=options,
            output=CommandOutput(
                write=self.stdout.write,
                success=self.style.SUCCESS,
                warning=self.style.WARNING,
            ),
        )
