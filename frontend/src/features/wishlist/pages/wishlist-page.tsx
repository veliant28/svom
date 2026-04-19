"use client";

import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { Link } from "@/i18n/navigation";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useWishlist } from "@/features/wishlist/hooks/use-wishlist";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { ContainedImagePanel } from "@/shared/components/ui/contained-image-panel";

export function WishlistPage() {
  const t = useTranslations("commerce.wishlist");
  const { isAuthenticated } = useAuth();
  const { items, isLoading } = useWishlist();

  if (!isAuthenticated) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("authRequired")}
        </p>
        <Link href="/login" className="mt-4 inline-flex rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          {t("goToLogin")}
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>

      <div className="mt-4">
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {t("states.loading")}
          </p>
        ) : items.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {t("states.empty")}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <ContainedImagePanel className="h-28 rounded-md" imageUrl={item.product.primary_image} />
                <p className="mt-3 line-clamp-2 text-sm font-semibold">{item.product.name}</p>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {item.product.brand_name}
                </p>
                <p className="mt-3 text-sm font-semibold whitespace-nowrap">
                  {item.product.final_price} {item.product.currency}
                </p>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="inline-flex gap-2">
                    <AddToCartButton productId={item.product.id} variant="headerGreenIcon" />
                    <WishlistToggleButton productId={item.product.id} />
                  </div>
                </div>
                <Link href={`/catalog/${item.product.slug}`} className="mt-4 inline-flex items-center gap-1 text-sm font-medium" style={{ color: "var(--accent)" }}>
                  {t("actions.viewProduct")}
                  <ArrowRight size={14} />
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
