import type { Dispatch, SetStateAction } from "react";

import { MonoPayWidget } from "@/features/checkout/components/payment/monopay-widget";
import { PaymentMethodToggle } from "@/features/checkout/components/payment/payment-method-toggle";
import type { CheckoutPaymentMethod, MonobankWidgetResponse } from "@/features/checkout/types/payment";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CheckoutPaymentSection({
  paymentMethod,
  comment,
  monobankWidgetLoading,
  monobankWidgetState,
  t,
  setPaymentMethod,
  setComment,
}: {
  paymentMethod: CheckoutPaymentMethod;
  comment: string;
  monobankWidgetLoading: boolean;
  monobankWidgetState: MonobankWidgetResponse | null;
  t: Translator;
  setPaymentMethod: Dispatch<SetStateAction<CheckoutPaymentMethod>>;
  setComment: Dispatch<SetStateAction<string>>;
}) {
  return (
    <>
      <h2 className="mt-5 text-lg font-semibold">{t("sections.payment")}</h2>
      <div className="mt-3 grid gap-3">
        <PaymentMethodToggle
          value={paymentMethod}
          onChange={setPaymentMethod}
          labels={{
            monobankTitle: t("payment.monobank"),
            monobankHint: t("payment.monobankHint"),
            codTitle: t("payment.cashOnDelivery"),
            codHint: t("payment.cashOnDeliveryHint"),
            novapayTitle: t("payment.novapay"),
            novapayHint: t("payment.novapayHint"),
            liqpayTitle: t("payment.liqpay"),
            liqpayHint: t("payment.liqpayHint"),
          }}
        />

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

        {monobankWidgetLoading ? (
          <p className="text-xs" style={{ color: "var(--muted)" }}>{t("payment.widgetLoading")}</p>
        ) : null}

        {monobankWidgetState && paymentMethod === "monobank" ? (
          <MonoPayWidget widget={monobankWidgetState.widget} pageUrl={monobankWidgetState.page_url} t={(key) => t(key)} />
        ) : null}
      </div>
    </>
  );
}
