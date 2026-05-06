from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.autodb.services.article_lookup import AutoDbArticleLookupService
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class ProductDiagnosis:
    product_id: str
    reason: str
    lookup_status: str
    has_raw_offers: bool
    brand_matched: bool
    article_found: bool
    link_possible: bool
    lookup_error: str = ""


class Command(BaseCommand):
    help = "Batch diagnostics for unlinked products against Auto_DB_Pro lookups."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--search", type=str, default="")
        parser.add_argument("--brand", type=str, default="")
        parser.add_argument("--allow-remote", action="store_true")

    def handle(self, *args, **options):
        limit = max(int(options.get("limit") or 100), 1)
        search = str(options.get("search") or "").strip()
        brand_filter = str(options.get("brand") or "").strip()
        allow_remote = bool(options.get("allow_remote"))
        remote_config_error = ""
        remote_check_completed = not allow_remote
        if allow_remote:
            try:
                AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
                remote_check_completed = True
            except AutoDbRemoteConfigError as exc:
                remote_config_error = str(exc)
                remote_check_completed = False

        lookup_service = AutoDbArticleLookupService()
        matcher = SupplierBrandMatcher()

        products = self._select_products(limit=limit, search=search, brand_filter=brand_filter)
        if not products:
            self.stdout.write("No unlinked products found.")
            return

        diagnoses: list[ProductDiagnosis] = []
        for product in products:
            item = self._diagnose_product(
                product=product,
                lookup_service=lookup_service,
                matcher=matcher,
                allow_remote=allow_remote,
                remote_config_error=remote_config_error,
            )
            diagnoses.append(item)
            self.stdout.write(
                f"- product_id={item.product_id} reason={item.reason} has_raw_offers={item.has_raw_offers} "
                f"brand_matched={item.brand_matched} article_found={item.article_found} link_possible={item.link_possible} "
                f"lookup_status={item.lookup_status}"
            )
            if item.lookup_error:
                self.stdout.write(f"  lookup_error={item.lookup_error}")

        self._print_summary(diagnoses, allow_remote=allow_remote, remote_check_completed=remote_check_completed)
        self.stdout.write("- UTR calls: 0")

    def _select_products(self, *, limit: int, search: str, brand_filter: str) -> list[Product]:
        qs = Product.objects.select_related("brand").filter(
            Q(autodb_supplier_id__isnull=True) | Q(autodb_article_number="")
        )
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(article__icontains=search) | Q(sku__icontains=search))
        if brand_filter:
            qs = qs.filter(brand__name__icontains=brand_filter)
        return list(qs.order_by("-updated_at")[:limit])

    def _diagnose_product(
        self,
        *,
        product: Product,
        lookup_service: AutoDbArticleLookupService,
        matcher: SupplierBrandMatcher,
        allow_remote: bool,
        remote_config_error: str,
    ) -> ProductDiagnosis:
        if remote_config_error:
            return ProductDiagnosis(
                product_id=str(product.id),
                reason="remote_config_error",
                lookup_status="lookup_not_completed",
                has_raw_offers=False,
                brand_matched=False,
                article_found=False,
                link_possible=False,
                lookup_error=remote_config_error,
            )

        raw_offers = self._collect_raw_offers(product=product)
        brand_candidates = self._collect_brand_candidates(product=product, raw_offers=raw_offers)
        article_candidates = self._collect_article_candidates(product=product, raw_offers=raw_offers)

        matcher_result = matcher.resolve_many(brand_candidates)
        brand_matched = any(
            bool(getattr(matcher_result.get(normalize_brand(item)), "matched_supplier_id", None))
            for item in brand_candidates
        )

        article_found = False
        lookup_error = ""
        for brand in brand_candidates[:3]:
            for article in article_candidates[:8]:
                try:
                    lookup = lookup_service.lookup(brand_name=brand, article=article, allow_remote=allow_remote)
                except Exception as exc:  # noqa: BLE001
                    lookup_error = str(exc)
                    continue
                if lookup.found:
                    article_found = True
                    break
            if article_found:
                break

        has_raw_offers = bool(raw_offers)
        link_possible = brand_matched and article_found
        lookup_not_completed = bool(allow_remote and lookup_error and not article_found)
        reason = self._resolve_reason(
            has_raw_offers=has_raw_offers,
            brand_matched=brand_matched,
            article_candidates=article_candidates,
            article_found=article_found,
            lookup_not_completed=lookup_not_completed,
        )

        return ProductDiagnosis(
            product_id=str(product.id),
            reason=reason,
            lookup_status="lookup_not_completed" if lookup_not_completed else "completed",
            has_raw_offers=has_raw_offers,
            brand_matched=brand_matched,
            article_found=article_found,
            link_possible=link_possible,
            lookup_error=lookup_error,
        )

    def _collect_raw_offers(self, *, product: Product) -> list[SupplierRawOffer]:
        filters = Q(matched_product=product)
        if product.article:
            filters |= Q(article__iexact=product.article)
        if product.sku:
            filters |= Q(external_sku__iexact=product.sku)
        return list(SupplierRawOffer.objects.filter(filters).order_by("-updated_at")[:20])

    def _collect_brand_candidates(self, *, product: Product, raw_offers: list[SupplierRawOffer]) -> list[str]:
        values = [str(getattr(product.brand, "name", "") or "")]
        values.extend(str(item.brand_name or "") for item in raw_offers)
        result: list[str] = []
        seen = set()
        for value in values:
            clean = value.strip()
            norm = normalize_brand(clean)
            if norm and norm not in seen:
                seen.add(norm)
                result.append(clean)
        return result

    def _collect_article_candidates(self, *, product: Product, raw_offers: list[SupplierRawOffer]) -> list[str]:
        values = [
            str(product.article or ""),
            str(product.sku or ""),
            str(product.autodb_article_number or ""),
        ]
        for offer in raw_offers:
            values.extend(
                [
                    str(offer.article or ""),
                    str(offer.external_sku or ""),
                    str((offer.raw_payload or {}).get("Артикул ТД") or ""),
                    str((offer.raw_payload or {}).get("article_td") or ""),
                    str((offer.raw_payload or {}).get("manufacturer_article") or ""),
                ]
            )

        result: list[str] = []
        seen = set()
        for item in values:
            clean = item.strip()
            if not clean:
                continue
            key = normalize_article(clean)
            if key and key not in seen:
                seen.add(key)
                result.append(clean)
        return result

    def _resolve_reason(
        self,
        *,
        has_raw_offers: bool,
        brand_matched: bool,
        article_candidates: list[str],
        article_found: bool,
        lookup_not_completed: bool,
    ) -> str:
        if lookup_not_completed:
            return "lookup_not_completed"
        if not has_raw_offers:
            return "no_raw_offers"
        if not brand_matched:
            return "brand_not_found"
        if not article_candidates:
            return "missing_article_candidates"
        if article_found:
            return "link_possible"
        return "needs_manual_mapping"

    def _print_summary(self, diagnoses: list[ProductDiagnosis], *, allow_remote: bool, remote_check_completed: bool) -> None:
        total = len(diagnoses)
        has_raw_offers = sum(1 for item in diagnoses if item.has_raw_offers)
        no_raw_offers = total - has_raw_offers
        brand_matched = sum(1 for item in diagnoses if item.brand_matched)
        article_found = sum(1 for item in diagnoses if item.article_found)
        article_not_found = total - article_found
        link_possible = sum(1 for item in diagnoses if item.link_possible)
        needs_manual_mapping = sum(1 for item in diagnoses if item.reason == "needs_manual_mapping")
        lookup_not_completed = sum(1 for item in diagnoses if item.reason == "lookup_not_completed")
        remote_config_error = sum(1 for item in diagnoses if item.reason == "remote_config_error")

        self.stdout.write("Summary:")
        self.stdout.write(f"- total_products_checked: {total}")
        self.stdout.write(f"- remote_requested: {'true' if allow_remote else 'false'}")
        self.stdout.write(f"- remote_check_completed: {'true' if remote_check_completed else 'false'}")
        self.stdout.write(f"- has_raw_offers: {has_raw_offers}")
        self.stdout.write(f"- no_raw_offers: {no_raw_offers}")
        self.stdout.write(f"- brand_matched: {brand_matched}")
        self.stdout.write(f"- article_found: {article_found}")
        self.stdout.write(f"- article_not_found: {article_not_found}")
        self.stdout.write(f"- linked_possible: {link_possible}")
        self.stdout.write(f"- needs_manual_mapping: {needs_manual_mapping}")
        self.stdout.write(f"- lookup_not_completed: {lookup_not_completed}")
        self.stdout.write(f"- remote_config_error: {remote_config_error}")
