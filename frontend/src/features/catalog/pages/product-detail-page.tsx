"use client";

import { ChevronLeft } from "lucide-react";
import { useTranslations } from "next-intl";

import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { useProductDetail } from "@/features/catalog/hooks/use-product-detail";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { Link } from "@/i18n/navigation";

import { ProductDetailSkeleton } from "../components/product-detail-skeleton";

export function ProductDetailPage({ slug }: { slug: string }) {
  const t = useTranslations("product.detail");
  const { product, isLoading } = useProductDetail(slug);

  if (isLoading) {
    return <ProductDetailSkeleton />;
  }

  if (!product) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <p>{t("notFound")}</p>
      </section>
    );
  }

  const images = Array.isArray(product.images) ? product.images : [];
  const attributes = Array.isArray(product.attributes) ? product.attributes : [];
  const fitments = Array.isArray(product.fitments) ? product.fitments : [];
  const primaryImage = images.find((image) => image.is_primary) ?? images[0];

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Link href="/catalog" className="inline-flex items-center gap-1 text-sm" style={{ color: "var(--muted)" }}>
        <ChevronLeft size={14} />
        {t("backToCatalog")}
      </Link>

      <div className="mt-4 grid gap-5 rounded-xl border p-6 md:grid-cols-[1.15fr_1fr]" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div
          className="min-h-[280px] rounded-lg bg-cover bg-center"
          style={{
            backgroundImage: primaryImage?.image_url ? `url(${primaryImage.image_url})` : "none",
            backgroundColor: "var(--surface-2)",
          }}
        />

        <div>
          <h1 className="text-2xl font-semibold">{product.name}</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {t("skuLabel")}: {product.sku} · {product.brand.name}
          </p>
          <p className="mt-4 text-xl font-semibold">
            {product.final_price} {product.currency}
          </p>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {product.availability_label}
            {product.estimated_delivery_days ? t("labels.eta", { days: product.estimated_delivery_days }) : ""}
          </p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            {product.procurement_source_summary}
          </p>
          <div className="mt-3 inline-flex gap-2">
            <AddToCartButton productId={product.id} />
            <WishlistToggleButton productId={product.id} />
          </div>
          <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>
            {product.short_description}
          </p>

          <div className="mt-5">
            <h2 className="text-sm font-semibold">{t("attributesTitle")}</h2>
            <ul className="mt-2 space-y-1 text-sm" style={{ color: "var(--muted)" }}>
              {attributes.map((attribute) => (
                <li key={attribute.id}>
                  {attribute.attribute_name}: {attribute.value}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-5">
            <h2 className="text-sm font-semibold">{t("fitmentTitle")}</h2>
            {fitments.length > 0 ? (
              <ul className="mt-2 space-y-2 text-sm" style={{ color: "var(--muted)" }}>
                {fitments.slice(0, 8).map((fitment) => (
                  <li key={fitment.id} className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)" }}>
                    <p>
                      {fitment.make} · {fitment.model} · {fitment.generation}
                    </p>
                    <p className="text-xs">
                      {fitment.engine} · {fitment.modification}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                {t("fitmentEmpty")}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
