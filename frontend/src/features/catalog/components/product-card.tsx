"use client";

import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { Link } from "@/i18n/navigation";
import type { CatalogProduct } from "@/features/catalog/types";

export function ProductCard({ product }: { product: CatalogProduct }) {
  const t = useTranslations("product.card");

  const fitmentBadge = (() => {
    if (product.fits_selected_vehicle === true) {
      return {
        label: t("fitment.fits"),
        color: "var(--success, #136f3a)",
        background: "color-mix(in srgb, var(--success, #136f3a) 10%, transparent)",
      };
    }

    if (!product.has_fitment_data) {
      return {
        label: t("fitment.noData"),
        color: "var(--muted)",
        background: "var(--surface-2)",
      };
    }

    if (product.fits_selected_vehicle === false) {
      return {
        label: t("fitment.notFits"),
        color: "var(--danger, #b42318)",
        background: "color-mix(in srgb, var(--danger, #b42318) 10%, transparent)",
      };
    }

    return null;
  })();

  return (
    <article className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div
        className="h-28 rounded-md bg-cover bg-center"
        style={{
          backgroundImage: product.primary_image ? `url(${product.primary_image})` : "none",
          backgroundColor: "var(--surface-2)",
        }}
      />

      <h3 className="mt-3 line-clamp-2 text-sm font-semibold">{product.name}</h3>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {product.brand?.name}
      </p>
      <p className="mt-3 text-sm font-semibold">
        {product.final_price} {product.currency}
      </p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {product.availability_label}
        {product.estimated_delivery_days ? t("labels.eta", { days: product.estimated_delivery_days }) : ""}
      </p>
      {fitmentBadge ? (
        <p
          className="mt-2 inline-flex rounded-full px-2 py-1 text-[11px] font-medium"
          style={{ color: fitmentBadge.color, backgroundColor: fitmentBadge.background }}
        >
          {fitmentBadge.label}
        </p>
      ) : null}

      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="inline-flex gap-2">
          <AddToCartButton productId={product.id} />
          <WishlistToggleButton productId={product.id} />
        </div>
      </div>

      <Link href={`/catalog/${product.slug}`} className="mt-4 inline-flex items-center gap-1 text-sm font-medium" style={{ color: "var(--accent)" }}>
        {t("viewDetails")}
        <ArrowRight size={14} />
      </Link>
    </article>
  );
}
