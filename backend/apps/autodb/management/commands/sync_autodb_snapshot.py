from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mysql.connector
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.autodb.models import (
    AutoDbArticle,
    AutoDbArticleAttribute,
    AutoDbArticleInfo,
    AutoDbArticleImage,
    AutoDbArticleLinkage,
    AutoDbArticleProductGroup,
    AutoDbManufacturer,
    AutoDbPassengerCar,
    AutoDbProductGroup,
    AutoDbSupplier,
    AutoDbVehicleModel,
)
from apps.autodb.services.intervals import parse_construction_interval
from apps.autodb.services.remote_config import AutoDbRemoteConfigValidator
from apps.catalog.services.category_management import normalized_category_name
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class SyncStats:
    suppliers: int = 0
    manufacturers: int = 0
    vehicle_models: int = 0
    passenger_cars: int = 0
    articles: int = 0
    article_linkages: int = 0
    article_images: int = 0
    article_attributes: int = 0
    article_infos: int = 0
    product_groups: int = 0
    article_product_groups: int = 0


class SyncProgressStore:
    def __init__(self, path: str | None):
        self.path = Path(path).expanduser() if path else None
        self.data: dict[str, Any] = {"stages": {}}
        if self.path and self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {"stages": {}}

        if not isinstance(self.data, dict):
            self.data = {"stages": {}}
        if "stages" not in self.data or not isinstance(self.data["stages"], dict):
            self.data["stages"] = {}

    def clear(self) -> None:
        self.data = {"stages": {}}
        self._save()

    def get_last_key(self, stage: str) -> dict[str, Any] | None:
        stages = self.data.get("stages", {})
        stage_entry = stages.get(stage)
        if not isinstance(stage_entry, dict):
            return None
        last_key = stage_entry.get("last_key")
        return last_key if isinstance(last_key, dict) else None

    def set_last_key(self, stage: str, *, key: dict[str, Any]) -> None:
        stage_entry = self._ensure_stage(stage)
        stage_entry["last_key"] = key
        stage_entry["completed"] = False
        stage_entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def mark_stage_completed(self, stage: str) -> None:
        stage_entry = self._ensure_stage(stage)
        stage_entry["completed"] = True
        stage_entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def reset_stage(self, stage: str) -> None:
        stage_entry = self._ensure_stage(stage)
        stage_entry["completed"] = False
        stage_entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def _ensure_stage(self, stage: str) -> dict[str, Any]:
        stages = self.data.setdefault("stages", {})
        stage_entry = stages.get(stage)
        if not isinstance(stage_entry, dict):
            stage_entry = {}
            stages[stage] = stage_entry
        return stage_entry

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)


class Command(BaseCommand):
    help = "Синхронизирует snapshot Auto-DB Pro (MySQL) в отдельную локальную PostgreSQL БД Auto_DB_Pro."
    STAGES = (
        "suppliers",
        "manufacturers",
        "models",
        "passenger_cars",
        "articles",
        "article_linkages",
        "article_images",
        "article_attributes",
        "product_groups",
        "article_product_groups",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Размер батча вставки в PostgreSQL.",
        )
        parser.add_argument(
            "--stage",
            choices=("all", *self.STAGES),
            default="all",
            help="Запустить один этап или полный sync.",
        )
        parser.add_argument(
            "--skip-truncate",
            action="store_true",
            help="Не очищать целевую БД перед запуском (нужно для resume/дозаливки).",
        )
        parser.add_argument(
            "--progress-file",
            default="",
            help="JSON-файл с row-level checkpoint для resume.",
        )
        parser.add_argument(
            "--resume-rows",
            action="store_true",
            help="Продолжать этап с последнего ключа из progress-file.",
        )

    def handle(self, *args, **options):
        batch_size = max(int(options["batch_size"]), 500)
        selected_stage = str(options["stage"])
        skip_truncate = bool(options["skip_truncate"])
        resume_rows = bool(options["resume_rows"])
        progress_file = str(options.get("progress_file") or "").strip()
        progress = SyncProgressStore(progress_file if progress_file else None)

        mysql_cfg = self._mysql_config()

        self.stdout.write(self.style.WARNING("[autodb-sync] start"))
        if not skip_truncate:
            self.stdout.write("[autodb-sync] truncating target tables ...")
            self._truncate_target()
            progress.clear()

        source = mysql.connector.connect(**mysql_cfg)
        try:
            stats = self._sync_selected(
                source=source,
                batch_size=batch_size,
                selected_stage=selected_stage,
                progress=progress,
                resume_rows=resume_rows,
            )
        finally:
            source.close()

        self.stdout.write(self.style.SUCCESS("[autodb-sync] done"))
        self.stdout.write(
            (
                "[autodb-sync] "
                f"suppliers={stats.suppliers} manufacturers={stats.manufacturers} "
                f"models={stats.vehicle_models} passenger_cars={stats.passenger_cars} "
                f"articles={stats.articles} article_linkages={stats.article_linkages} "
                f"article_images={stats.article_images} article_attributes={stats.article_attributes} "
                f"article_infos={stats.article_infos} "
                f"product_groups={stats.product_groups} article_product_groups={stats.article_product_groups}"
            )
        )

    def _mysql_config(self) -> dict:
        snapshot = AutoDbRemoteConfigValidator.snapshot()
        host = str(snapshot.host or "").strip()
        database = str(snapshot.database or "").strip()
        user = str(snapshot.user or "").strip()
        password = str(snapshot.password or "").strip()
        if not host or not database or not user:
            raise CommandError(
                "AutoDB remote settings in DB are incomplete: host/database/user are required."
            )

        return {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
            "connection_timeout": int(getattr(settings, "AUTODB_SOURCE_MYSQL_TIMEOUT_SECONDS", snapshot.connect_timeout)),
            "charset": "utf8mb4",
            "use_unicode": True,
        }

    def _sync_selected(
        self,
        *,
        source,
        batch_size: int,
        selected_stage: str,
        progress: SyncProgressStore,
        resume_rows: bool,
    ) -> SyncStats:
        stats = SyncStats()
        stages = self.STAGES if selected_stage == "all" else (selected_stage,)
        for stage in stages:
            progress.reset_stage(stage)
            stats = self._run_stage(
                stage=stage,
                source=source,
                batch_size=batch_size,
                stats=stats,
                progress=progress,
                resume_rows=resume_rows,
            )
            progress.mark_stage_completed(stage)
        return stats

    def _run_stage(
        self,
        *,
        stage: str,
        source,
        batch_size: int,
        stats: SyncStats,
        progress: SyncProgressStore,
        resume_rows: bool,
    ) -> SyncStats:
        if stage == "suppliers":
            count = self._sync_suppliers(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=count,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "manufacturers":
            count = self._sync_manufacturers(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=count,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "models":
            count = self._sync_models(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=count,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "passenger_cars":
            count = self._sync_passenger_cars(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=count,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "articles":
            count = self._sync_articles(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=count,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "article_linkages":
            count = self._sync_article_linkages(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=count,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "article_images":
            count = self._sync_article_images(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=count,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "article_attributes":
            count = self._sync_article_attributes(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=count,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "article_infos":
            count = self._sync_article_infos(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=count,
                product_groups=stats.product_groups,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "product_groups":
            count = self._sync_product_groups(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=count,
                article_product_groups=stats.article_product_groups,
            )

        if stage == "article_product_groups":
            count = self._sync_article_product_groups(source=source, batch_size=batch_size, progress=progress, resume_rows=resume_rows)
            return SyncStats(
                suppliers=stats.suppliers,
                manufacturers=stats.manufacturers,
                vehicle_models=stats.vehicle_models,
                passenger_cars=stats.passenger_cars,
                articles=stats.articles,
                article_linkages=stats.article_linkages,
                article_images=stats.article_images,
                article_attributes=stats.article_attributes,
                article_infos=stats.article_infos,
                product_groups=stats.product_groups,
                article_product_groups=count,
            )

        raise CommandError(f"Unsupported stage: {stage}")

    def _truncate_target(self) -> None:
        tables = [
            AutoDbArticleProductGroup._meta.db_table,
            AutoDbProductGroup._meta.db_table,
            AutoDbArticleInfo._meta.db_table,
            AutoDbArticleAttribute._meta.db_table,
            AutoDbArticleImage._meta.db_table,
            AutoDbArticleLinkage._meta.db_table,
            AutoDbArticle._meta.db_table,
            AutoDbPassengerCar._meta.db_table,
            AutoDbVehicleModel._meta.db_table,
            AutoDbManufacturer._meta.db_table,
            AutoDbSupplier._meta.db_table,
        ]
        with transaction.atomic(using="auto_db_pro"):
            with transaction.get_connection(using="auto_db_pro").cursor() as cursor:
                for table in tables:
                    cursor.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

    def _sync_suppliers(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbSupplier,
            stage="suppliers",
            label="suppliers",
            key_names=("id",),
            select_sql="SELECT id, description, matchcode FROM suppliers",
            build=lambda r: AutoDbSupplier(
                id=int(r[0]),
                name=str(r[1] or "").strip(),
                matchcode=str(r[2] or "").strip(),
                normalized_name=normalize_brand(str(r[1] or "")),
                normalized_matchcode=normalize_brand(str(r[2] or "")),
            ),
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_manufacturers(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbManufacturer,
            stage="manufacturers",
            label="manufacturers",
            key_names=("id",),
            select_sql="SELECT id, description, matchcode FROM manufacturers",
            build=lambda r: AutoDbManufacturer(
                id=int(r[0]),
                description=str(r[1] or "").strip(),
                matchcode=str(r[2] or "").strip(),
            ),
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_models(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        def build(row):
            manufacturer_id = row[1]
            if manufacturer_id is None:
                return None
            return AutoDbVehicleModel(
                id=int(row[0]),
                manufacturer_id=int(manufacturer_id),
                description=str(row[2] or "").strip(),
                full_description=str(row[3] or "").strip(),
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbVehicleModel,
            stage="models",
            label="models",
            key_names=("id",),
            select_sql="SELECT id, manufacturerid, description, fulldescription FROM models",
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_passenger_cars(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        def build(row):
            model_id = row[1]
            if model_id is None:
                return None
            interval = str(row[4] or "").strip()
            start_year, start_month, end_year, end_month = parse_construction_interval(interval)
            return AutoDbPassengerCar(
                id=int(row[0]),
                model_id=int(model_id),
                description=str(row[2] or "").strip(),
                full_description=str(row[3] or "").strip(),
                construction_interval=interval,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbPassengerCar,
            stage="passenger_cars",
            label="passanger_cars",
            key_names=("id",),
            select_sql="SELECT id, modelid, description, fulldescription, constructioninterval FROM passanger_cars",
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_articles(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        def build(row):
            article_number = str(row[1] or "").strip()
            if not article_number:
                return None
            return AutoDbArticle(
                supplier_id=int(row[0]),
                article_number=article_number,
                normalized_article=normalize_article(article_number),
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbArticle,
            stage="articles",
            label="articles",
            key_names=("supplierId", "DataSupplierArticleNumber"),
            select_sql="SELECT supplierId, DataSupplierArticleNumber FROM articles",
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_article_linkages(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        def build(row):
            supplier_id = int(row[0])
            article_number = str(row[1] or "").strip()
            if not article_number:
                return None
            linkage_type = str(row[2] or "").strip()
            linkage_id = row[3]
            if not linkage_type or linkage_id is None:
                return None
            return AutoDbArticleLinkage(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                linkage_type=linkage_type,
                linkage_id=int(linkage_id),
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbArticleLinkage,
            stage="article_linkages",
            label="article_li",
            key_names=("supplierId", "DataSupplierArticleNumber", "linkageTypeId", "linkageId"),
            select_sql="SELECT supplierId, DataSupplierArticleNumber, linkageTypeId, linkageId FROM article_li",
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_article_images(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        table = "article_images"
        columns = self._table_columns(source=source, table=table)
        supplier_col = self._pick_column(columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo"))
        article_col = self._pick_column(columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
        if not supplier_col or not article_col:
            self.stdout.write(self.style.WARNING("[autodb-sync] article_images: no supplier/article columns, skipped"))
            return 0

        image_url_col = self._pick_column(columns, ("fullImagePath", "imageUrl", "url", "image"))
        image_path_col = self._pick_column(columns, ("imagePath", "path", "filePath", "file"))
        extension_col = self._pick_column(columns, ("extension", "fileExt", "imageExt", "fileExtension", "type"))
        primary_col = self._pick_column(columns, ("isPrimary", "primary", "isMain", "main"))
        sort_col = self._pick_column(columns, ("sortOrder", "sort", "position", "seqNo", "orderNo"))
        image_url_expr = image_url_col or "''"
        image_path_expr = image_path_col or "''"
        extension_expr = extension_col or "''"
        primary_expr = primary_col or "0"
        sort_expr = sort_col or "0"

        select_sql = (
            f"SELECT {supplier_col}, {article_col}, "
            f"{image_url_expr}, "
            f"{image_path_expr}, "
            f"{extension_expr}, "
            f"{primary_expr}, "
            f"{sort_expr} "
            f"FROM {table}"
        )

        def build(row):
            supplier_id = self._to_int(row[0])
            article_number = str(row[1] or "").strip()
            if not supplier_id or not article_number:
                return None
            image_url = str(row[2] or "").strip()
            image_path = str(row[3] or "").strip()
            if not image_url and not image_path:
                return None
            return AutoDbArticleImage(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                image_url=image_url,
                image_path=image_path,
                file_extension=str(row[4] or "").strip()[:16],
                is_primary=self._to_bool(row[5]),
                sort_order=self._to_int(row[6], default=0),
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbArticleImage,
            stage="article_images",
            label="article_images",
            key_names=(supplier_col, article_col),
            select_sql=select_sql,
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_article_attributes(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        table = "article_attributes"
        columns = self._table_columns(source=source, table=table)
        supplier_col = self._pick_column(columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo"))
        article_col = self._pick_column(columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
        name_col = self._pick_column(columns, ("attributeName", "name", "title", "criterionName", "criteriaName"))
        value_col = self._pick_column(columns, ("attributeValue", "value", "criterionValue", "criteriaValue"))
        if not supplier_col or not article_col or not name_col:
            self.stdout.write(self.style.WARNING("[autodb-sync] article_attributes: no required columns, skipped"))
            return 0

        unit_col = self._pick_column(columns, ("unit", "measureUnit", "uom"))
        sort_col = self._pick_column(columns, ("sortOrder", "sort", "position", "seqNo", "orderNo"))
        value_expr = value_col or "''"
        unit_expr = unit_col or "''"
        sort_expr = sort_col or "0"

        select_sql = (
            f"SELECT {supplier_col}, {article_col}, {name_col}, {value_expr}, "
            f"{unit_expr}, {sort_expr} "
            f"FROM {table}"
        )

        def build(row):
            supplier_id = self._to_int(row[0])
            article_number = str(row[1] or "").strip()
            attr_name = str(row[2] or "").strip()
            if not supplier_id or not article_number or not attr_name:
                return None
            return AutoDbArticleAttribute(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                attribute_name=attr_name[:255],
                attribute_value=str(row[3] or "").strip(),
                unit=str(row[4] or "").strip()[:64],
                sort_order=self._to_int(row[5], default=0),
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbArticleAttribute,
            stage="article_attributes",
            label="article_attributes",
            key_names=(supplier_col, article_col),
            select_sql=select_sql,
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_article_infos(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        table = "article_inf"
        columns = self._table_columns(source=source, table=table)
        supplier_col = self._pick_column(columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo", "DLNr"))
        article_col = self._pick_column(columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
        text_col = self._pick_column(
            columns,
            ("text", "infoText", "informationText", "information", "description", "txt", "value", "name", "title"),
        )
        if not supplier_col or not article_col or not text_col:
            self.stdout.write(self.style.WARNING("[autodb-sync] article_inf: no required columns, skipped"))
            return 0

        id_col = self._pick_column(columns, ("id", "infId", "infoId"))
        lang_col = self._pick_column(columns, ("language", "languageId", "lang", "langId", "countryCode"))
        type_col = self._pick_column(columns, ("infoType", "informationType", "informationTypeKey", "type", "infType", "kind"))
        sort_col = self._pick_column(columns, ("sortOrder", "sort", "position", "seqNo", "orderNo", "SortNo"))
        lang_expr = lang_col or "''"
        type_expr = type_col or "''"
        sort_expr = sort_col or "0"

        select_parts = []
        if id_col:
            select_parts.append(id_col)
        select_parts.extend([supplier_col, article_col, text_col, lang_expr, type_expr, sort_expr])
        select_sql = f"SELECT {', '.join(select_parts)} FROM {table}"
        key_names: tuple[str, ...]
        if id_col:
            key_names = (id_col,)
        else:
            key_names = (supplier_col, article_col, text_col)

        def build(row):
            offset = 1 if id_col else 0
            supplier_id = self._to_int(row[offset + 0])
            article_number = str(row[offset + 1] or "").strip()
            info_text = " ".join(str(row[offset + 2] or "").strip().split())
            if not supplier_id or not article_number or not info_text:
                return None
            return AutoDbArticleInfo(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                info_text=info_text,
                info_language=str(row[offset + 3] or "").strip()[:32],
                info_type=str(row[offset + 4] or "").strip()[:64],
                sort_order=self._to_int(row[offset + 5], default=0) or 0,
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbArticleInfo,
            stage="article_infos",
            label="article_inf",
            key_names=key_names,
            select_sql=select_sql,
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_product_groups(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        table = "prd"
        columns = self._table_columns(source=source, table=table)
        id_col = self._pick_column(columns, ("id", "prdId", "productId", "PT_ID"))
        name_col = self._pick_column(columns, ("description", "name", "title", "text", "PT_TEXT", "fullDescription"))
        if not id_col:
            self.stdout.write(self.style.WARNING("[autodb-sync] prd: no id column, skipped"))
            return 0

        name_expr = name_col or "''"
        select_sql = f"SELECT {id_col}, {name_expr} FROM {table}"

        def build(row):
            group_id = self._to_int(row[0])
            if not group_id:
                return None
            name = str(row[1] or "").strip()
            return AutoDbProductGroup(
                id=group_id,
                name=name[:255],
                normalized_name=normalized_category_name(name)[:255],
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbProductGroup,
            stage="product_groups",
            label="prd",
            key_names=(id_col,),
            select_sql=select_sql,
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _sync_article_product_groups(self, *, source, batch_size: int, progress: SyncProgressStore, resume_rows: bool) -> int:
        table = "article_prd"
        columns = self._table_columns(source=source, table=table)
        supplier_col = self._pick_column(columns, ("supplierId", "sup_id", "ART_SUP_ID", "BrandNo"))
        article_col = self._pick_column(columns, ("DataSupplierArticleNumber", "articleNumber", "ART_ARTICLE_NR", "ArtNo"))
        group_col = self._pick_column(columns, ("prdId", "productId", "groupId", "PT_ID", "GenArtNo"))

        if not supplier_col or not article_col or not group_col:
            self.stdout.write(self.style.WARNING("[autodb-sync] article_prd: no required columns, skipped"))
            return 0

        select_sql = f"SELECT {supplier_col}, {article_col}, {group_col} FROM {table}"

        def build(row):
            supplier_id = self._to_int(row[0])
            article_number = str(row[1] or "").strip()
            group_id = self._to_int(row[2])
            if not supplier_id or not article_number or not group_id:
                return None
            return AutoDbArticleProductGroup(
                supplier_id=supplier_id,
                article_number=article_number,
                normalized_article=normalize_article(article_number),
                product_group_id=group_id,
            )

        return self._bulk_sync_keyset(
            source=source,
            model=AutoDbArticleProductGroup,
            stage="article_product_groups",
            label="article_prd",
            key_names=(supplier_col, article_col, group_col),
            select_sql=select_sql,
            build=build,
            batch_size=batch_size,
            progress=progress,
            resume_rows=resume_rows,
        )

    def _bulk_sync_keyset(
        self,
        *,
        source,
        model,
        stage: str,
        label: str,
        key_names: tuple[str, ...],
        select_sql: str,
        build,
        batch_size: int,
        progress: SyncProgressStore,
        resume_rows: bool,
    ) -> int:
        self.stdout.write(f"[autodb-sync] syncing {label} ...")
        inserted = 0

        key_values: tuple[Any, ...] | None = None
        if resume_rows:
            stored = progress.get_last_key(stage)
            if stored:
                try:
                    key_values = tuple(stored[name] for name in key_names)
                    self.stdout.write(f"[autodb-sync] {label}: resume_from={stored}")
                except KeyError:
                    key_values = None

        cursor = source.cursor()
        try:
            while True:
                sql, params = self._build_keyset_query(
                    select_sql=select_sql,
                    key_names=key_names,
                    key_values=key_values,
                    batch_size=batch_size,
                )
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                if not rows:
                    break

                buffer = []
                for row in rows:
                    entity = build(row)
                    if entity is not None:
                        buffer.append(entity)

                if buffer:
                    model.objects.using("auto_db_pro").bulk_create(buffer, batch_size=batch_size, ignore_conflicts=True)
                    inserted += len(buffer)
                    self.stdout.write(f"[autodb-sync] {label}: inserted={inserted}")

                last_row = rows[-1]
                key_values = tuple(last_row[i] for i in range(len(key_names)))
                progress.set_last_key(
                    stage,
                    key={key_names[i]: key_values[i] for i in range(len(key_names))},
                )

                if len(rows) < batch_size:
                    break
        finally:
            try:
                cursor.close()
            except Exception:
                pass

        return inserted

    def _build_keyset_query(
        self,
        *,
        select_sql: str,
        key_names: tuple[str, ...],
        key_values: tuple[Any, ...] | None,
        batch_size: int,
    ) -> tuple[str, tuple[Any, ...]]:
        order_clause = ", ".join(key_names)

        if not key_values:
            return f"{select_sql} ORDER BY {order_clause} LIMIT %s", (batch_size,)

        if len(key_names) == 1:
            where = f"{key_names[0]} > %s"
            params: tuple[Any, ...] = (key_values[0], batch_size)
            return f"{select_sql} WHERE {where} ORDER BY {order_clause} LIMIT %s", params

        left = ", ".join(key_names)
        placeholders = ", ".join(["%s"] * len(key_names))
        where = f"({left}) > ({placeholders})"
        params = (*key_values, batch_size)
        return f"{select_sql} WHERE {where} ORDER BY {order_clause} LIMIT %s", params

    def _table_columns(self, *, source, table: str) -> list[str]:
        cursor = source.cursor()
        try:
            cursor.execute(f"SHOW COLUMNS FROM {table}")
            return [str(row[0]) for row in cursor.fetchall()]
        except Exception:
            return []
        finally:
            cursor.close()

    @staticmethod
    def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
        by_lower = {value.lower(): value for value in columns}
        for candidate in candidates:
            actual = by_lower.get(candidate.lower())
            if actual:
                return actual
        return None

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        normalized = str(value).strip().lower()
        return normalized in {"1", "true", "t", "yes", "y"}

    @staticmethod
    def _to_int(value: Any, *, default: int | None = None) -> int | None:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
