"use client";

import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { CartProductQuantityStepper } from "@/features/cart/components/cart-product-quantity-stepper";
import { CartSummaryBlock } from "@/features/cart/components/cart-summary-block";
import { useCart } from "@/features/cart/hooks/use-cart";
import { Link } from "@/i18n/navigation";

export function CartPage() {
  const t = useTranslations("commerce.cart");
  const { isAuthenticated } = useAuth();
  const { cart, isLoading, removeItem } = useCart();

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
            {items.map((item) => {
              return (
                <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate text-sm font-semibold">{item.product.name}</p>
                    <div className="inline-flex items-center gap-3 shrink-0">
                      <CartProductQuantityStepper productId={item.product.id} maxQuantity={item.max_order_quantity} />
                      <div className="inline-flex items-center gap-2">
                        <p className="text-sm font-semibold tabular-nums whitespace-nowrap">
                          {item.line_total} {item.product.currency}
                        </p>
                        <span className="group relative inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                            style={{
                              borderColor: "#ef4444",
                              backgroundColor: "var(--surface)",
                              color: "#dc2626",
                            }}
                            aria-label={t("actions.remove")}
                            onClick={() => void removeItem(item.id)}
                          >
                            <Trash2 size={14} />
                          </button>
                          <span role="tooltip" className="header-tooltip hidden group-hover:block">
                            {t("actions.remove")}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                    {item.product.brand_name}
                  </p>
                  {item.warning ? (
                    <p className="mt-1 text-xs" style={{ color: "var(--danger, #b42318)" }}>
                      {item.warning}
                    </p>
                  ) : null}

                </article>
              );
            })}
          </div>

          <div className="space-y-3">
            <CartSummaryBlock
              itemsCount={cart?.summary?.items_count ?? 0}
              subtotal={cart?.summary?.subtotal ?? "0.00"}
              currency={cart?.currency ?? "UAH"}
            />
            <Link
              href="/checkout"
              className="inline-flex w-full justify-center rounded-md border px-3 py-2 text-sm !text-white transition-colors hover:border-[#356f49] hover:bg-[#3f8258]"
              style={{ borderColor: "#3f8a5a", backgroundColor: "#4b9264", color: "#ffffff" }}
            >
              {t("actions.checkout")}
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
