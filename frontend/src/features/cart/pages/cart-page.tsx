"use client";

import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { CartSummaryBlock } from "@/features/cart/components/cart-summary-block";
import { useCart } from "@/features/cart/hooks/use-cart";
import { Link } from "@/i18n/navigation";

export function CartPage() {
  const t = useTranslations("commerce.cart");
  const { isAuthenticated } = useAuth();
  const { cart, isLoading, updateItemQuantity, removeItem } = useCart();

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

  const items = Array.isArray(cart?.items) ? cart?.items : [];

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>

      {isLoading ? (
        <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>
          {t("states.loading")}
        </p>
      ) : items.length === 0 ? (
        <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>
          {t("states.empty")}
        </p>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_300px]">
          <div className="space-y-3">
            {(cart?.summary?.warnings_count ?? 0) > 0 ? (
              <div className="rounded-xl border px-3 py-2 text-sm" style={{ borderColor: "var(--danger, #b42318)", backgroundColor: "color-mix(in srgb, var(--danger, #b42318) 8%, transparent)" }}>
                {t("warnings.availabilityOrPriceChanged")}
              </div>
            ) : null}
            {items.map((item) => (
              <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <p className="text-sm font-semibold">{item.product.name}</p>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {item.product.brand_name}
                </p>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {item.availability_label}
                  {item.estimated_delivery_days ? t("labels.eta", { days: item.estimated_delivery_days }) : ""}
                </p>
                {item.warning ? (
                  <p className="mt-1 text-xs" style={{ color: "var(--danger, #b42318)" }}>
                    {item.warning}
                  </p>
                ) : null}

                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="inline-flex items-center gap-2">
                    <button
                      type="button"
                      className="h-8 rounded-md border px-2 text-xs"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      onClick={() => void updateItemQuantity(item.id, Math.max(item.quantity - 1, 0))}
                    >
                      -
                    </button>
                    <span className="text-sm">{item.quantity}</span>
                    <button
                      type="button"
                      className="h-8 rounded-md border px-2 text-xs"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      onClick={() => void updateItemQuantity(item.id, item.quantity + 1)}
                    >
                      +
                    </button>
                  </div>

                  <div className="text-right">
                    <p className="text-sm font-semibold">
                      {item.line_total} {item.product.currency}
                    </p>
                    <button
                      type="button"
                      className="mt-1 text-xs"
                      style={{ color: "var(--danger, #b42318)" }}
                      onClick={() => void removeItem(item.id)}
                    >
                      {t("actions.remove")}
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="space-y-3">
            <CartSummaryBlock
              itemsCount={cart?.summary?.items_count ?? 0}
              subtotal={cart?.summary?.subtotal ?? "0.00"}
              currency={cart?.currency ?? "UAH"}
            />
            <Link
              href="/checkout"
              className="inline-flex w-full justify-center rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              {t("actions.checkout")}
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
