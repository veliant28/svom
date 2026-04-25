import { Check, Loader2, X } from "lucide-react";
import type { KeyboardEvent } from "react";

import { CartSummaryBlock } from "@/features/cart/components/cart-summary-block";
import type { Cart, CheckoutPreview } from "@/features/commerce/types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CheckoutSidebar({
  cart,
  preview,
  promoInput,
  appliedPromoCode,
  isPromoApplying,
  t,
  onPromoInputChange,
  onPromoInputKeyDown,
  onApplyPromo,
  onClearPromo,
}: {
  cart: Cart;
  preview: CheckoutPreview | null;
  promoInput: string;
  appliedPromoCode: string;
  isPromoApplying: boolean;
  t: Translator;
  onPromoInputChange: (value: string) => void;
  onPromoInputKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onApplyPromo: () => void;
  onClearPromo: () => void;
}) {
  return (
    <div className="space-y-3">
      <CartSummaryBlock
        itemsCount={preview?.items_count ?? cart.summary.items_count}
        subtotal={preview?.subtotal ?? cart.summary.subtotal}
        currency={cart.currency}
      />

      <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{t("sections.promo")}</h2>
        <div className="mt-2 grid gap-2">
          <div className="flex gap-2">
            <input
              value={promoInput}
              onChange={(event) => onPromoInputChange(event.target.value.toUpperCase())}
              onKeyDown={onPromoInputKeyDown}
              placeholder={t("promo.placeholder")}
              className="h-9 min-w-0 flex-1 rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
            <span className="group relative inline-flex">
              <button
                type="button"
                aria-label={isPromoApplying ? t("promo.actions.applying") : t("promo.actions.apply")}
                disabled={isPromoApplying || !promoInput.trim()}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border disabled:opacity-60"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={onApplyPromo}
              >
                {isPromoApplying ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
              </button>
              <span role="tooltip" className="header-tooltip hidden group-hover:block group-focus-within:block">
                {isPromoApplying ? t("promo.actions.applying") : t("promo.actions.apply")}
              </span>
            </span>
            {appliedPromoCode ? (
              <span className="group relative inline-flex">
                <button
                  type="button"
                  aria-label={t("promo.actions.clear")}
                  disabled={isPromoApplying}
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  onClick={onClearPromo}
                >
                  <X size={15} />
                </button>
                <span role="tooltip" className="header-tooltip hidden group-hover:block group-focus-within:block">
                  {t("promo.actions.clear")}
                </span>
              </span>
            ) : null}
          </div>

          {preview?.promo ? (
            <div className="rounded-lg border p-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p><span style={{ color: "var(--muted)" }}>{t("promo.labels.code")}:</span> <strong>{preview.promo.code}</strong></p>
              <p className="mt-1">
                <span style={{ color: "var(--muted)" }}>{t("promo.labels.type")}:</span>{" "}
                {preview.promo.discount_type === "delivery_fee" ? t("promo.types.delivery") : t("promo.types.product")}
              </p>
              <p className="mt-1">
                <span style={{ color: "var(--muted)" }}>{t("promo.labels.discount")}:</span>{" "}
                {preview.promo.total_discount} {cart.currency}
              </p>
              {preview.promo.delivery_discount !== "0.00" ? (
                <p className="mt-1">
                  <span style={{ color: "var(--muted)" }}>{t("promo.labels.deliverySavings")}:</span>{" "}
                  {preview.promo.delivery_discount} {cart.currency}
                </p>
              ) : null}
              {preview.promo.product_discount !== "0.00" ? (
                <p className="mt-1">
                  <span style={{ color: "var(--muted)" }}>{t("promo.labels.productSavings")}:</span>{" "}
                  {preview.promo.product_discount} {cart.currency}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{t("sections.orderReview")}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("review.deliveryFee", { fee: preview?.delivery_fee ?? "0.00", currency: cart.currency })}
        </p>
        {(preview?.discount_total ?? "0.00") !== "0.00" ? (
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {t("review.discount", { amount: preview?.discount_total ?? "0.00", currency: cart.currency })}
          </p>
        ) : null}
        <p className="mt-1 text-sm font-semibold">
          {t("review.total", { total: preview?.total ?? cart.summary.subtotal, currency: cart.currency })}
        </p>
      </div>
    </div>
  );
}
