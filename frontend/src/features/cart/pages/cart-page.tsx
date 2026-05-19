"use client";

import { Minus, Plus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { CartSummaryBlock } from "@/features/cart/components/cart-summary-block";
import { useCart } from "@/features/cart/hooks/use-cart";
import { Link } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function CartPage() {
  const t = useTranslations("commerce.cart");
  const { isAuthenticated } = useAuth();
  const { cart, isLoading, removeItem, setProductQuantity } = useCart();
  const { showInfo } = useStorefrontFeedback();
  const lastWarningToastKeyRef = useRef("");
  const [pendingProductId, setPendingProductId] = useState<string | null>(null);
  const items = Array.isArray(cart?.items) ? cart?.items : [];

  useEffect(() => {
    if (!isAuthenticated || isLoading) {
      return;
    }

    const hasWarnings = (cart?.summary?.warnings_count ?? 0) > 0;
    if (!hasWarnings) {
      lastWarningToastKeyRef.current = "";
      return;
    }

    const warningText = t("warnings.availabilityOrPriceChanged");
    if (lastWarningToastKeyRef.current === warningText) {
      return;
    }
    lastWarningToastKeyRef.current = warningText;
    showInfo(warningText);
  }, [cart?.summary?.warnings_count, isAuthenticated, isLoading, showInfo, t]);

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
            {items.map((item) => {
              const quantity = Math.max(0, Number(item.quantity || 0));
              const displayName = String(item.product.name || "").trim();
              const displaySku = String(item.product.sku || "").trim();
              const displayBrand = String(item.product.brand_name || "").trim();
              const displayArticle = String(item.product.article || item.product.manufacturer_article || "").trim();
              const maxQuantity = typeof item.max_order_quantity === "number" && Number.isFinite(item.max_order_quantity)
                ? Math.max(0, Math.floor(item.max_order_quantity))
                : Number.MAX_SAFE_INTEGER;
              const isPending = pendingProductId === item.product.id;

              async function updateQuantity(next: number) {
                if (isPending) {
                  return;
                }
                setPendingProductId(item.product.id);
                try {
                  await setProductQuantity(item.product.id, Math.max(0, next), item.max_order_quantity);
                } finally {
                  setPendingProductId((current) => (current === item.product.id ? null : current));
                }
              }

              return (
                <article key={item.id} className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <div className="grid gap-3 sm:grid-cols-[68px_minmax(0,1fr)_auto] sm:items-center">
                    <div className="h-[68px] w-[68px] overflow-hidden rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      {item.product.primary_image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={item.product.primary_image} alt={displayName} className="h-full w-full object-cover" />
                      ) : null}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate font-semibold">{displayName}</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>
                        {t("labels.skuLine", {
                          sku: displaySku || "—",
                          brand: displayBrand || "—",
                          article: displayArticle || "—",
                        })}
                      </p>
                    </div>

                    <div className="inline-flex items-center gap-2">
                      <div
                        className="inline-flex h-8 items-center rounded-full border px-1"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      >
                        <button
                          type="button"
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                          onClick={() => {
                            void updateQuantity(quantity - 1);
                          }}
                          disabled={isPending || quantity <= 0}
                          aria-label={t("actions.remove")}
                        >
                          <Minus className="h-3.5 w-3.5" />
                        </button>
                        <span className="inline-flex h-6 min-w-[2rem] items-center justify-center px-2 text-xs font-semibold tabular-nums">
                          {quantity}
                        </span>
                        <button
                          type="button"
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                          onClick={() => {
                            void updateQuantity(quantity + 1);
                          }}
                          disabled={isPending || quantity >= maxQuantity}
                          aria-label={t("actions.add")}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <p className="inline-flex h-8 items-center text-sm font-semibold tabular-nums whitespace-nowrap">
                        {item.unit_price} {item.product.currency}
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
                          onClick={() => {
                            if (!isPending) {
                              void removeItem(item.id);
                            }
                          }}
                          disabled={isPending}
                        >
                          <Trash2 size={14} />
                        </button>
                        <span role="tooltip" className="header-tooltip hidden group-hover:block">
                          {t("actions.remove")}
                        </span>
                      </span>
                    </div>
                  </div>
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
