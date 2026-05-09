"use client";

import { type MouseEvent } from "react";
import { ArrowRight, Boxes, CheckCircle2, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { Link } from "@/i18n/navigation";
import type { CatalogProduct } from "@/features/catalog/types";
import { ContainedImagePanel } from "@/shared/components/ui/contained-image-panel";
import { getCurrentCatalogUrl, saveCatalogReturnState } from "@/features/catalog/lib/catalog-navigation-state";
import { resolveCompatibilityBadgeState } from "@/features/catalog/lib/compatibility-badge";

export function ProductCard({
  product,
  preserveCatalogQuery = false,
}: {
  product: CatalogProduct;
  preserveCatalogQuery?: boolean;
}) {
  const t = useTranslations("product.card");
  const searchParams = useSearchParams();
  const stockTone: BackofficeStatusChipTone =
    product.total_stock_qty <= 0 ? "red" : product.total_stock_qty <= 5 ? "orange" : "blue";
  const sanitizedDetailQuery = (() => {
    if (!preserveCatalogQuery) {
      return "";
    }
    const params = new URLSearchParams(searchParams.toString());
    params.delete("_cs");
    params.delete("_csr");
    params.delete("_cy");
    return params.toString();
  })();
  const productHref = (() => {
    return sanitizedDetailQuery ? `/catalog/${product.slug}?${sanitizedDetailQuery}` : `/catalog/${product.slug}`;
  })();
  const handleDetailClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (
      !preserveCatalogQuery
      || event.button !== 0
      || event.metaKey
      || event.ctrlKey
      || event.shiftKey
      || event.altKey
    ) {
      return;
    }

    const catalogUrl = getCurrentCatalogUrl();
    if (!catalogUrl || typeof window === "undefined") {
      return;
    }

    const productNode = event.currentTarget.closest<HTMLElement>("[data-catalog-product-id]");
    saveCatalogReturnState({
      catalogUrl,
      productId: product.id,
      scrollY: window.scrollY,
      productViewportTop: productNode?.getBoundingClientRect().top ?? 0,
    });
  };

  const fitmentBadge = (() => {
    const selectedVehicleCompatible = product.selected_vehicle_compatibility?.is_compatible;
    const state = resolveCompatibilityBadgeState({
      fitsSelectedVehicle:
        typeof selectedVehicleCompatible === "boolean" ? selectedVehicleCompatible : product.fits_selected_vehicle,
      hasFitmentData: product.has_fitment_data,
      isAutoDbCompatibleDataAvailable: product.is_autodb_compatible_data_available,
      suppressIncompatibleBadge: product.vehicle_filter_policy === "show_all_with_badges",
    });

    if (state === "fits") {
      return {
        label: t("fitment.fits"),
        tone: "success" as const,
        icon: CheckCircle2,
      };
    }

    if (state === "not_fits") {
      return {
        label: t("fitment.notFits"),
        tone: "red" as const,
        icon: XCircle,
      };
    }

    if (state === "has_data") {
      return {
        label: t("fitment.hasData"),
        tone: "blue" as const,
        icon: CheckCircle2,
      };
    }

    return null;
  })();

  return (
    <article
      data-catalog-product-id={product.id}
      className="flex h-full flex-col rounded-xl border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
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
        scroll
        onClick={handleDetailClick}
        className="mt-auto pt-4 inline-flex items-center gap-1 text-sm font-medium"
        style={{ color: "var(--accent)" }}
      >
        {t("viewDetails")}
        <ArrowRight size={14} />
      </Link>
    </article>
  );
}
