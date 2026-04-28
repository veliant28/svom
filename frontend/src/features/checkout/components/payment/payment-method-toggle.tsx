import { CodPaymentCard } from "@/features/checkout/components/payment/cod-payment-card";
import { LiqpayPaymentCard } from "@/features/checkout/components/payment/liqpay-payment-card";
import { MonobankPaymentCard } from "@/features/checkout/components/payment/monobank-payment-card";
import { NovapayPaymentCard } from "@/features/checkout/components/payment/novapay-payment-card";
import type { CheckoutPaymentMethod } from "@/features/checkout/types/payment";

export function PaymentMethodToggle({
  value,
  onChange,
  availableMethods,
  labels,
}: {
  value: CheckoutPaymentMethod;
  onChange: (next: CheckoutPaymentMethod) => void;
  availableMethods: CheckoutPaymentMethod[];
  labels: {
    monobankTitle: string;
    monobankHint: string;
    codTitle: string;
    codHint: string;
    novapayTitle: string;
    novapayHint: string;
    liqpayTitle: string;
    liqpayHint: string;
  };
}) {
  const methods = new Set(availableMethods);
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))]">
      {methods.has("cash_on_delivery") ? (
        <CodPaymentCard
          title={labels.codTitle}
          hint={labels.codHint}
          selected={value === "cash_on_delivery"}
          onSelect={() => onChange("cash_on_delivery")}
        />
      ) : null}
      {methods.has("monobank") ? (
        <MonobankPaymentCard
          title={labels.monobankTitle}
          hint={labels.monobankHint}
          selected={value === "monobank"}
          onSelect={() => onChange("monobank")}
        />
      ) : null}
      {methods.has("novapay") ? (
        <NovapayPaymentCard
          title={labels.novapayTitle}
          hint={labels.novapayHint}
          selected={value === "novapay"}
          onSelect={() => onChange("novapay")}
        />
      ) : null}
      {methods.has("liqpay") ? (
        <LiqpayPaymentCard
          title={labels.liqpayTitle}
          hint={labels.liqpayHint}
          selected={value === "liqpay"}
          onSelect={() => onChange("liqpay")}
        />
      ) : null}
    </div>
  );
}
