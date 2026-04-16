"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { CartSummaryBlock } from "@/features/cart/components/cart-summary-block";
import { useCart } from "@/features/cart/hooks/use-cart";
import { getCheckoutPreview } from "@/features/checkout/api/get-checkout-preview";
import { submitCheckout } from "@/features/checkout/api/submit-checkout";
import type { CheckoutPreview, Order } from "@/features/commerce/types";
import { Link } from "@/i18n/navigation";
import { isApiRequestError } from "@/shared/api/http-client";

export function CheckoutPage() {
  const t = useTranslations("commerce.checkout");
  const { token, isAuthenticated, user } = useAuth();
  const { cart, refresh } = useCart();

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState(user?.email ?? "");
  const [deliveryMethod, setDeliveryMethod] = useState<Order["delivery_method"]>("pickup");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<Order["payment_method"]>("card_placeholder");
  const [comment, setComment] = useState("");
  const [preview, setPreview] = useState<CheckoutPreview | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successOrderNumber, setSuccessOrderNumber] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEmail(user?.email ?? "");
  }, [user?.email]);

  useEffect(() => {
    let isMounted = true;

    async function loadPreview() {
      if (!token || !isAuthenticated) {
        if (isMounted) {
          setPreview(null);
        }
        return;
      }

      try {
        const response = await getCheckoutPreview(token, deliveryMethod);
        if (isMounted) {
          setPreview(response.checkout_preview);
        }
      } catch {
        if (isMounted) {
          setPreview(null);
        }
      }
    }

    void loadPreview();

    return () => {
      isMounted = false;
    };
  }, [token, isAuthenticated, deliveryMethod, cart?.updated_at]);

  const requiresAddress = useMemo(
    () => deliveryMethod === "courier" || deliveryMethod === "nova_poshta",
    [deliveryMethod],
  );

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

  if (!cart || cart.items.length === 0) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("emptyCart")}
        </p>
        <Link href="/catalog" className="mt-4 inline-flex rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          {t("goToCatalog")}
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
      {(preview?.warnings?.length ?? 0) > 0 ? (
        <div className="mt-3 rounded-xl border px-3 py-2 text-sm" style={{ borderColor: "var(--danger, #b42318)", backgroundColor: "color-mix(in srgb, var(--danger, #b42318) 8%, transparent)" }}>
          {preview?.warnings.map((warning) => (
            <p key={warning.product_id}>
              {warning.product_name}: {warning.warning}
            </p>
          ))}
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_320px]">
        <form
          className="rounded-xl border p-4"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onSubmit={async (event) => {
            event.preventDefault();
            if (!token) {
              return;
            }

            setError(null);
            setSuccessOrderNumber(null);
            setIsSubmitting(true);
            try {
              const order = await submitCheckout(token, {
                contact_full_name: fullName,
                contact_phone: phone,
                contact_email: email,
                delivery_method: deliveryMethod,
                delivery_address: deliveryAddress,
                payment_method: paymentMethod,
                customer_comment: comment,
              });
              setSuccessOrderNumber(order.order_number);
              await refresh();
            } catch (submitError) {
              if (isApiRequestError(submitError)) {
                setError(submitError.message);
              } else {
                setError(t("submitError"));
              }
            } finally {
              setIsSubmitting(false);
            }
          }}
        >
          <h2 className="text-lg font-semibold">{t("sections.contact")}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs sm:col-span-2">
              {t("fields.fullName")}
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              {t("fields.phone")}
              <input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              {t("fields.email")}
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>
          </div>

          <h2 className="mt-5 text-lg font-semibold">{t("sections.delivery")}</h2>
          <div className="mt-3 grid gap-3">
            <label className="flex flex-col gap-1 text-xs">
              {t("fields.deliveryMethod")}
              <select
                value={deliveryMethod}
                onChange={(event) => setDeliveryMethod(event.target.value as Order["delivery_method"])}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              >
                <option value="pickup">{t("delivery.pickup")}</option>
                <option value="courier">{t("delivery.courier")}</option>
                <option value="nova_poshta">{t("delivery.novaPoshta")}</option>
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs">
              {t("fields.deliveryAddress")}
              <input
                value={deliveryAddress}
                onChange={(event) => setDeliveryAddress(event.target.value)}
                required={requiresAddress}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>
          </div>

          <h2 className="mt-5 text-lg font-semibold">{t("sections.payment")}</h2>
          <div className="mt-3 grid gap-3">
            <label className="flex flex-col gap-1 text-xs">
              {t("fields.paymentMethod")}
              <select
                value={paymentMethod}
                onChange={(event) => setPaymentMethod(event.target.value as Order["payment_method"])}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              >
                <option value="card_placeholder">{t("payment.cardPlaceholder")}</option>
                <option value="cash_on_delivery">{t("payment.cashOnDelivery")}</option>
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs">
              {t("fields.comment")}
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={3}
                className="rounded-md border px-3 py-2"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-4 inline-flex rounded-md border px-4 py-2 text-sm disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {isSubmitting ? t("actions.submitting") : t("actions.submit")}
          </button>

          {successOrderNumber ? (
            <p className="mt-3 text-sm" style={{ color: "var(--success, #136f3a)" }}>
              {t("success", { orderNumber: successOrderNumber })}
            </p>
          ) : null}

          {error ? (
            <p className="mt-3 text-sm" style={{ color: "var(--danger, #b42318)" }}>
              {error}
            </p>
          ) : null}
        </form>

        <div className="space-y-3">
          <CartSummaryBlock
            itemsCount={preview?.items_count ?? cart.summary.items_count}
            subtotal={preview?.subtotal ?? cart.summary.subtotal}
            currency={cart.currency}
          />

          <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <h2 className="text-sm font-semibold">{t("sections.orderReview")}</h2>
            <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
              {t("review.deliveryFee", { fee: preview?.delivery_fee ?? "0.00", currency: cart.currency })}
            </p>
            <p className="mt-1 text-sm font-semibold">
              {t("review.total", { total: preview?.total ?? cart.summary.subtotal, currency: cart.currency })}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
