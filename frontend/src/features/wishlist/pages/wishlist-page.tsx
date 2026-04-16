"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useWishlist } from "@/features/wishlist/hooks/use-wishlist";

export function WishlistPage() {
  const t = useTranslations("commerce.wishlist");
  const { isAuthenticated } = useAuth();
  const { items, isLoading, toggleWishlist } = useWishlist();

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
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {items.map((item) => (
              <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <p className="text-sm font-semibold">{item.product.name}</p>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {item.product.brand_name}
                </p>
                <p className="mt-2 text-sm font-semibold">
                  {item.product.final_price} {item.product.currency}
                </p>
                <div className="mt-3 flex gap-2">
                  <Link href={`/catalog/${item.product.slug}`} className="rounded-md border px-3 py-1.5 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                    {t("actions.viewProduct")}
                  </Link>
                  <button
                    type="button"
                    onClick={() => void toggleWishlist(item.product.id)}
                    className="rounded-md border px-3 py-1.5 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  >
                    {t("actions.remove")}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
