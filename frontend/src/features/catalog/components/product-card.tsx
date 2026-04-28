"use client";

import { type MouseEvent } from "react";
import { ArrowRight, Boxes, CheckCircle2, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { Link } from "@/i18n/navigation";
import { useRouter } from "@/i18n/navigation";
import type { CatalogProduct } from "@/features/catalog/types";
import { ContainedImagePanel } from "@/shared/components/ui/contained-image-panel";
import { isFitmentDisabledCategory } from "@/features/catalog/lib/fitment-disabled-categories";

export function ProductCard({
  product,
  preserveCatalogQuery = false,
}: {
  product: CatalogProduct;
  preserveCatalogQuery?: boolean;
}) {
  const t = useTranslations("product.card");
  const searchParams = useSearchParams();
  const router = useRouter();
  const stockTone: BackofficeStatusChipTone =
    product.total_stock_qty <= 0 ? "red" : product.total_stock_qty <= 5 ? "orange" : "blue";
  const productHref = (() => {
    const query = preserveCatalogQuery ? searchParams.toString() : "";
    return query ? `/catalog/${product.slug}?${query}` : `/catalog/${product.slug}`;
  })();
  const normalizeUrlForStorage = (rawUrl: string): string => {
    try {
      const parsed = rawUrl.startsWith("http://") || rawUrl.startsWith("https://")
        ? new URL(rawUrl)
        : new URL(rawUrl, "http://localhost");
      const params = new URLSearchParams(parsed.search);
      const sortedEntries = Array.from(params.entries()).sort(([a], [b]) => a.localeCompare(b));
      const normalized = new URLSearchParams();
      for (const [key, value] of sortedEntries) {
        normalized.append(key, value);
      }
      const query = normalized.toString();
      return query ? `${parsed.pathname}?${query}` : parsed.pathname;
    } catch {
      return rawUrl;
    }
  };
  const handleOpenDetails = (event: MouseEvent<HTMLAnchorElement>) => {
    if (typeof window === "undefined") {
      return;
    }

    if (preserveCatalogQuery) {
      const detailParams = new URLSearchParams(searchParams.toString());
      detailParams.delete("_cs");
      const detailQuery = detailParams.toString();
      const detailHref = detailQuery ? `/catalog/${product.slug}?${detailQuery}` : `/catalog/${product.slug}`;

      const catalogParams = new URLSearchParams(detailParams.toString());
      catalogParams.set("_cs", String(Math.max(0, Math.floor(window.scrollY))));
      const catalogQueryWithScroll = catalogParams.toString();
      const catalogUrlWithScroll = catalogQueryWithScroll
        ? `${window.location.pathname}?${catalogQueryWithScroll}`
        : window.location.pathname;

      event.preventDefault();
      window.history.replaceState(window.history.state, "", catalogUrlWithScroll);
      router.push(detailHref, { scroll: false });

      try {
        const normalizedCatalogUrl = normalizeUrlForStorage(catalogUrlWithScroll);
        window.sessionStorage.setItem(
          `catalog:scroll:${normalizedCatalogUrl}`,
          JSON.stringify({
            y: window.scrollY,
            savedAt: Date.now(),
          }),
        );
      } catch {
        // Best-effort cache only.
      }
    }
  };

  const fitmentBadge = (() => {
    if (product.fitment_badge_hidden || isFitmentDisabledCategory(product.category)) {
      return null;
    }

    if (product.fits_selected_vehicle === true) {
      return {
        label: t("fitment.fits"),
        tone: "success" as const,
        icon: CheckCircle2,
      };
    }

    if (product.fits_selected_vehicle === false) {
      return {
        label: t("fitment.notFits"),
        tone: "red" as const,
        icon: XCircle,
      };
    }

    return null;
  })();

  return (
    <article className="flex h-full flex-col rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <ContainedImagePanel className="h-28 rounded-md" imageUrl={product.primary_image} />

      <h3 className="mt-3 min-h-[2.75rem] line-clamp-2 text-sm font-semibold">{product.name}</h3>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {product.brand?.name}
      </p>
      <div className="mt-3 flex items-center justify-between gap-2">
        <p className="text-sm font-semibold whitespace-nowrap">
          {product.final_price} {product.currency}
        </p>
        <BackofficeStatusChip tone={stockTone} icon={Boxes} className="shrink-0">
          {t("labels.stockTotal", { count: product.total_stock_qty })}
        </BackofficeStatusChip>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="inline-flex gap-2">
          <AddToCartButton productId={product.id} variant="headerGreenIcon" maxQuantity={product.total_stock_qty} />
          <WishlistToggleButton productId={product.id} />
        </div>
        {fitmentBadge ? (
          <BackofficeStatusChip tone={fitmentBadge.tone} icon={fitmentBadge.icon} className="shrink-0">
            {fitmentBadge.label}
          </BackofficeStatusChip>
        ) : null}
      </div>

      <Link
        href={productHref}
        scroll={false}
        onClick={handleOpenDetails}
        className="mt-auto pt-4 inline-flex items-center gap-1 text-sm font-medium"
        style={{ color: "var(--accent)" }}
      >
        {t("viewDetails")}
        <ArrowRight size={14} />
      </Link>
    </article>
  );
}
