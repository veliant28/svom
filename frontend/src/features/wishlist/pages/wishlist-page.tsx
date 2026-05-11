"use client";

import { useTranslations } from "next-intl";

import { ProductCard } from "@/features/catalog/components/product-card";
import { Link } from "@/i18n/navigation";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useWishlist } from "@/features/wishlist/hooks/use-wishlist";

export function WishlistPage() {
  const t = useTranslations("commerce.wishlist");
  const { isAuthenticated } = useAuth();
  const { items, isLoading } = useWishlist();
  const visibleItems = items.filter((item) => Boolean(item.product));

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
        ) : visibleItems.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {t("states.empty")}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {visibleItems.map((item) => (
              item.product ? <ProductCard key={item.id} product={item.product} /> : null
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
