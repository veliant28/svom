"use client";

import { Boxes, ChevronLeft } from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { CartProductQuantityStepper } from "@/features/cart/components/cart-product-quantity-stepper";
import { useProductDetail } from "@/features/catalog/hooks/use-product-detail";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { Link } from "@/i18n/navigation";
import { ContainedImagePanel } from "@/shared/components/ui/contained-image-panel";

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
  const stockTone: BackofficeStatusChipTone =
    product.total_stock_qty <= 0 ? "red" : product.total_stock_qty <= 5 ? "orange" : "blue";

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Link href="/catalog" className="inline-flex items-center gap-1 text-sm" style={{ color: "var(--muted)" }}>
        <ChevronLeft size={14} />
        {t("backToCatalog")}
      </Link>

      <div className="mt-4 grid gap-5 rounded-xl border p-6 md:grid-cols-[1.15fr_1fr]" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <ContainedImagePanel className="min-h-[280px] rounded-lg" imageUrl={primaryImage?.image_url} />

        <div>
          <h1 className="text-2xl font-semibold">{product.name}</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {t("skuLabel")}: {product.sku} · {product.brand.name}
          </p>
          <div className="mt-4 grid grid-cols-[max-content_1fr_max-content] items-center gap-3">
            <p className="text-xl font-semibold whitespace-nowrap">
              {product.final_price} {product.currency}
            </p>
            <div className="flex justify-center">
              <CartProductQuantityStepper productId={product.id} maxQuantity={product.total_stock_qty} />
            </div>
            <div className="flex justify-end">
              <BackofficeStatusChip tone={stockTone} icon={Boxes} className="shrink-0">
                {t("labels.stockTotal", { count: product.total_stock_qty })}
              </BackofficeStatusChip>
            </div>
          </div>
          <div className="mt-3 inline-flex gap-2">
            <AddToCartButton productId={product.id} variant="headerGreenIconLg" maxQuantity={product.total_stock_qty} />
            <WishlistToggleButton productId={product.id} variant="headerIconLg" />
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
