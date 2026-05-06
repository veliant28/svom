from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, QuerySet

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.pricing.services import ProductSellableSnapshotService
from apps.search.services import ProductSearchService
from apps.search.services.elasticsearch_client import (
    get_elasticsearch_client,
    get_products_index_name,
    is_elasticsearch_enabled,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class LookupDiagnostics:
    route: str
    lookup_value: str
    would_resolve: bool
    reason: str


class Command(BaseCommand):
    help = "Diagnose why catalog product detail may return 404 and inspect product/source/search state."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", type=str, default="", help="Product UUID")
        parser.add_argument("--slug", type=str, default="", help="Product slug or potential lookup token")
        parser.add_argument("--search", type=str, default="", help="Search token (name/article/sku/code)")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        slug = str(options.get("slug") or "").strip()
        search = str(options.get("search") or "").strip()
        if not any([product_id, slug, search]):
            raise CommandError("Pass one of: --product-id, --slug, --search")

        queryset = Product.objects.select_related("brand", "category", "product_price").order_by("id")
        candidates = self._resolve_candidates(queryset, product_id=product_id, slug=slug, search=search)

        self.stdout.write("diagnose_product_detail:")
        self.stdout.write(f"- route: /api/catalog/products/<slug>/")
        self.stdout.write(f"- lookup mode: slug primary, fallback by article/autodb_article_number/sku")
        self.stdout.write(f"- query.product_id: {product_id or '-'}")
        self.stdout.write(f"- query.slug: {slug or '-'}")
        self.stdout.write(f"- query.search: {search or '-'}")
        self.stdout.write(f"- product exists: {'yes' if candidates.exists() else 'no'}")
        self.stdout.write(f"- candidate_count: {candidates.count()}")

        if not candidates.exists():
            self.stdout.write("- why_404: no Product matched provided selector.")
            self.stdout.write("- UTR calls: 0")
            return

        for index, product in enumerate(candidates[:20], start=1):
            self._print_product_diagnostics(
                index=index,
                product=product,
                lookup_value=slug or search or str(product.id),
            )
        self.stdout.write("- UTR calls: 0")

    def _resolve_candidates(
        self,
        queryset: QuerySet[Product],
        *,
        product_id: str,
        slug: str,
        search: str,
    ) -> QuerySet[Product]:
        if product_id:
            return queryset.filter(id=product_id)
        if slug:
            return queryset.filter(
                Q(slug__iexact=slug)
                | Q(article__iexact=slug)
                | Q(autodb_article_number__iexact=slug)
                | Q(sku__iexact=slug)
            )
        return queryset.filter(
            Q(name__icontains=search)
            | Q(name_uk__icontains=search)
            | Q(name_ru__icontains=search)
            | Q(name_en__icontains=search)
            | Q(article__icontains=search)
            | Q(autodb_article_number__icontains=search)
            | Q(sku__icontains=search)
            | Q(slug__icontains=search)
            | Q(brand__name__icontains=search)
        )

    def _print_product_diagnostics(self, *, index: int, product: Product, lookup_value: str) -> None:
        snapshot = ProductSellableSnapshotService().build(product=product, quantity=1)
        supplier_offer_qs = SupplierOffer.objects.filter(product=product).select_related("supplier")
        best_offer = supplier_offer_qs.order_by("supplier__priority", "-stock_qty", "id").first()
        raw_qs = SupplierRawOffer.objects.filter(
            Q(matched_product=product)
            | Q(article__iexact=product.article)
            | Q(external_sku__iexact=product.sku)
        ).order_by("-updated_at", "-id")
        detail_lookup = self._diagnose_detail_lookup(product=product, lookup_value=lookup_value)
        search_presence = self._diagnose_search_presence(product=product, query_hint=lookup_value)

        self.stdout.write(f"- [{index}] id={product.id}")
        self.stdout.write(f"  exists=yes")
        self.stdout.write(f"  slug={product.slug or '-'}")
        self.stdout.write(f"  name={product.name or '-'}")
        self.stdout.write(f"  name_uk={product.name_uk or '-'}")
        self.stdout.write(f"  name_ru={product.name_ru or '-'}")
        self.stdout.write(f"  name_en={product.name_en or '-'}")
        self.stdout.write(f"  brand={product.brand.name if product.brand_id else '-'}")
        self.stdout.write(f"  article={product.article or '-'}")
        self.stdout.write(f"  active={product.is_active}")
        self.stdout.write(f"  published_at={product.published_at.isoformat() if product.published_at else '-'}")
        self.stdout.write(f"  category={product.category.name if product.category_id else '-'}")
        self.stdout.write(
            f"  price_cached={getattr(getattr(product, 'product_price', None), 'final_price', '-') or '-'} "
            f"currency={getattr(getattr(product, 'product_price', None), 'currency', '-') or '-'} "
            f"stock_cached={product.available_stock_qty_cached}"
        )
        self.stdout.write(
            f"  best_supplier_offer={best_offer.id if best_offer else '-'} "
            f"supplier={best_offer.supplier.name if best_offer else '-'} stock={best_offer.stock_qty if best_offer else '-'}"
        )
        self.stdout.write(f"  sellable.selected_offer_id={snapshot.selected_offer_id or '-'}")
        self.stdout.write(f"  supplier_offer_count={supplier_offer_qs.count()}")
        self.stdout.write(f"  supplier_raw_offer_candidates={raw_qs.count()}")
        for raw in raw_qs.values("id", "article", "external_sku", "product_name")[:5]:
            self.stdout.write(
                f"    raw_offer id={raw['id']} article={raw.get('article') or '-'} "
                f"external_sku={raw.get('external_sku') or '-'} product_name={raw.get('product_name') or '-'}"
            )
        self.stdout.write(f"  why_detail_api_404={detail_lookup.reason}")
        self.stdout.write(f"  route_expected={detail_lookup.route}")
        self.stdout.write(f"  lookup_value={detail_lookup.lookup_value or '-'}")
        self.stdout.write(f"  lookup_would_resolve={detail_lookup.would_resolve}")
        self.stdout.write(f"  search_has_product={search_presence}")

    def _diagnose_detail_lookup(self, *, product: Product, lookup_value: str) -> LookupDiagnostics:
        if not product.is_active:
            return LookupDiagnostics(
                route="/api/catalog/products/<slug>/",
                lookup_value=lookup_value,
                would_resolve=False,
                reason="product_inactive",
            )

        lookup = str(lookup_value or "").strip()
        if not lookup:
            return LookupDiagnostics(
                route="/api/catalog/products/<slug>/",
                lookup_value=lookup,
                would_resolve=False,
                reason="empty_lookup",
            )

        if product.slug.lower() == lookup.lower():
            return LookupDiagnostics(
                route="/api/catalog/products/<slug>/",
                lookup_value=lookup,
                would_resolve=True,
                reason="matched_by_slug",
            )

        if lookup.lower() in {
            str(product.article or "").lower(),
            str(product.autodb_article_number or "").lower(),
            str(product.sku or "").lower(),
        }:
            return LookupDiagnostics(
                route="/api/catalog/products/<slug>/",
                lookup_value=lookup,
                would_resolve=True,
                reason="matched_by_fallback_identifier",
            )

        return LookupDiagnostics(
            route="/api/catalog/products/<slug>/",
            lookup_value=lookup,
            would_resolve=False,
            reason="lookup_token_does_not_match_slug_or_fallback_identifiers",
        )

    def _diagnose_search_presence(self, *, product: Product, query_hint: str) -> str:
        token = str(query_hint or "").strip() or str(product.article or "") or str(product.sku or "") or str(product.id)
        db_query = ProductSearchService().apply(Product.objects.filter(is_active=True), token)
        in_db_search = db_query.filter(id=product.id).exists()

        elastic_status = "disabled"
        if is_elasticsearch_enabled():
            client = get_elasticsearch_client()
            if client is None:
                elastic_status = "enabled_no_client"
            else:
                try:
                    response = client.search(
                        index=get_products_index_name(),
                        body={
                            "query": {"term": {"_id": str(product.id)}},
                            "size": 1,
                        },
                    )
                    total = int(response.get("hits", {}).get("total", {}).get("value", 0))
                    elastic_status = "hit" if total > 0 else "miss"
                except Exception as exc:  # noqa: BLE001
                    elastic_status = f"error:{exc.__class__.__name__}"

        return f"db_search={'yes' if in_db_search else 'no'} elastic={elastic_status}"
