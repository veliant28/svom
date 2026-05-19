"use client";

import { ArrowLeft, Minus, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { createReturnRequest, getEligibleReturnOrderDetail } from "@/features/commerce/api/returns-api";
import { formatReturnMoney } from "@/features/account/lib/returns-formatters";
import type { EligibleReturnOrderDetail } from "@/features/commerce/types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link, useRouter } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

const RETURN_REASON_MIN_LENGTH = 10;

export function AccountReturnsCreateOrderPage({ orderId }: { orderId: string }) {
  const t = useTranslations("commerce.returns");
  const tCart = useTranslations("commerce.cart");
  const locale = useLocale();
  const { token, user, isAuthenticated } = useAuth();
  const { showApiError, showError, showInfo, showSuccess } = useStorefrontFeedback();
  const router = useRouter();

  const [data, setData] = useState<EligibleReturnOrderDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [reasonComment, setReasonComment] = useState("");
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const shownNonReturnableToast = useRef(false);

  useEffect(() => {
    if (!isAuthenticated || !user) {
      return;
    }
    if (!user.returns_enabled) {
      router.replace("/account/orders");
    }
  }, [isAuthenticated, router, user]);

  useEffect(() => {
    let mounted = true;

    async function load() {
      if (!token || !isAuthenticated || !user?.returns_enabled) {
        if (mounted) {
          setData(null);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const payload = await getEligibleReturnOrderDetail(token, orderId);
        if (!mounted) {
          return;
        }

        const initialQuantities: Record<string, number> = {};
        for (const item of payload.items) {
          if (item.is_returnable && item.max_return_quantity > 0) {
            initialQuantities[item.order_item_id] = item.max_return_quantity;
          }
        }

        setData(payload);
        setQuantities(initialQuantities);

        if (!shownNonReturnableToast.current && payload.items.some((item) => !item.is_returnable)) {
          shownNonReturnableToast.current = true;
          showInfo(t("toasts.someItemsNonReturnable"));
        }
      } catch (error) {
        if (mounted) {
          setData(null);
        }
        showApiError(error, t("states.eligibleLoadFailed"));
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, orderId, showApiError, showInfo, t, token, user?.returns_enabled]);

  const selectedRows = useMemo(() => {
    if (!data) {
      return [];
    }
    return data.items.filter((item) => item.is_returnable && (quantities[item.order_item_id] || 0) > 0);
  }, [data, quantities]);

  const totalItems = useMemo(() => {
    return selectedRows.reduce((acc, row) => acc + (quantities[row.order_item_id] || 0), 0);
  }, [quantities, selectedRows]);

  const totalAmount = useMemo(() => {
    return selectedRows.reduce((acc, row) => {
      const qty = quantities[row.order_item_id] || 0;
      const price = Number(row.unit_price || "0");
      if (!Number.isFinite(price)) {
        return acc;
      }
      return acc + price * qty;
    }, 0);
  }, [quantities, selectedRows]);

  const reasonLength = reasonComment.trim().length;
  const canSubmit = selectedRows.length > 0 && reasonLength >= RETURN_REASON_MIN_LENGTH && !isSubmitting;

  function updateQuantity(orderItemId: string, next: number, max: number) {
    const clamped = Math.max(0, Math.min(max, next));
    setQuantities((prev) => {
      if (clamped <= 0) {
        const copy = { ...prev };
        delete copy[orderItemId];
        return copy;
      }
      return { ...prev, [orderItemId]: clamped };
    });
  }

  async function handleSubmit() {
    if (!token || !data || isSubmitting) {
      return;
    }
    if (!selectedRows.length) {
      showError(t("toasts.selectItem"));
      return;
    }
    if (reasonLength < RETURN_REASON_MIN_LENGTH) {
      showError(t("toasts.reasonRequired"));
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = await createReturnRequest(token, {
        order_id: data.order.id,
        items: selectedRows.map((row) => ({
          order_item_id: row.order_item_id,
          quantity: quantities[row.order_item_id] || 0,
        })),
        reason_comment: reasonComment.trim(),
      });
      showSuccess(t("toasts.created"));
      router.push(`/account/returns/${payload.id}`);
    } catch (error) {
      showApiError(error, t("toasts.createFailed"));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{t("createByOrder.title")}</h1>
          <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
            {data ? t("createByOrder.orderLabel", { order: data.order.order_number, day: data.order.return_day_label }) : ""}
          </p>
        </div>
        <Link
          href="/account/returns/create"
          className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition hover:opacity-80"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--accent)" }}
        >
          <ArrowLeft size={14} />
          <span>{t("actions.backToOrders").replace("← ", "")}</span>
        </Link>
      </div>

      {isLoading ? <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>{t("states.loading")}</p> : null}

      {!isLoading && data ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_300px]">
          <div className="space-y-3">
            {data.items.map((item) => {
              const quantity = quantities[item.order_item_id] || 0;
              const isDisabled = !item.is_returnable || item.max_return_quantity <= 0;
              const displayName = String(item.product?.name || item.product_name || "").trim();
              const displaySku = String(item.product?.sku || item.product_sku || "").trim();
              const displayBrand = String(item.product?.brand_name || "").trim();
              const displayArticle = String(item.product?.article || "").trim();
              const skuMetaParts = [displaySku, displayBrand, displayArticle].filter(Boolean);

              return (
                <article
                  key={item.order_item_id}
                  className="rounded-xl border p-3"
                  style={{
                    borderColor: "var(--border)",
                    backgroundColor: "var(--surface)",
                    opacity: isDisabled ? 0.65 : 1,
                  }}
                >
                  <div className="grid gap-3 sm:grid-cols-[68px_minmax(0,1fr)_auto] sm:items-center">
                    <div className="h-[68px] w-[68px] overflow-hidden rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      {item.product?.primary_image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={item.product.primary_image} alt={displayName} className="h-full w-full object-cover" />
                      ) : null}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate font-semibold">{displayName}</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>
                        SKU: {skuMetaParts.join(" · ")}
                      </p>
                      {isDisabled ? <p className="text-xs" style={{ color: "var(--muted)" }}>{item.non_returnable_reason || t("labels.nonReturnable")}</p> : null}
                    </div>

                    <div className="flex items-center gap-2">
                      {!isDisabled ? (
                        <div className="inline-flex items-center gap-2">
                          <div
                            className="inline-flex h-8 items-center rounded-full border px-1"
                            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          >
                            <button
                              type="button"
                              className="inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                              onClick={() => updateQuantity(item.order_item_id, quantity - 1, item.max_return_quantity)}
                              disabled={quantity <= 0}
                              aria-label={t("actions.removeItem")}
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
                              onClick={() => updateQuantity(item.order_item_id, quantity + 1, item.max_return_quantity)}
                              disabled={quantity >= item.max_return_quantity}
                              aria-label="+"
                            >
                              <Plus className="h-3.5 w-3.5" />
                            </button>
                          </div>

                          <p className="inline-flex h-8 items-center text-sm font-semibold tabular-nums whitespace-nowrap">
                            {formatReturnMoney(item.unit_price, locale, data.order.currency)}
                          </p>

                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors hover:opacity-90"
                            style={{ borderColor: "#ef4444", backgroundColor: "var(--surface)", color: "#dc2626" }}
                            onClick={() => updateQuantity(item.order_item_id, 0, item.max_return_quantity)}
                            aria-label={t("actions.removeItem")}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs" style={{ color: "var(--muted)" }}>—</span>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          <div className="space-y-3">
            <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <h2 className="text-lg font-semibold">{tCart("summary.title")}</h2>
              <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                {tCart("summary.items", { count: totalItems })}
              </p>
              <p className="mt-2 text-xl font-semibold">
                {formatReturnMoney(String(totalAmount), locale, data.order.currency)}
              </p>

              <label className="mt-3 grid gap-1">
                <span className="text-sm font-semibold">{t("fields.reason")}</span>
                <textarea
                  value={reasonComment}
                  onChange={(event) => setReasonComment(event.target.value)}
                  className="min-h-24 rounded-md border p-2 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  placeholder={t("fields.reasonPlaceholder")}
                />
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {t("fields.reasonMinHint", { min: RETURN_REASON_MIN_LENGTH, current: reasonLength })}
                </p>
              </label>
            </div>

            <button
              type="button"
              className="inline-flex w-full justify-center rounded-md border px-3 py-2 text-sm !text-white transition-colors hover:border-[#356f49] hover:bg-[#3f8258] disabled:opacity-60"
              style={{ borderColor: "#3f8a5a", backgroundColor: "#4b9264", color: "#ffffff" }}
              onClick={() => { void handleSubmit(); }}
              disabled={!canSubmit}
            >
              {isSubmitting ? t("actions.submitting") : t("actions.submit")}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
