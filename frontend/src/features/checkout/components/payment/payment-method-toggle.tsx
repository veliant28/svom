import { CodPaymentCard } from "@/features/checkout/components/payment/cod-payment-card";
import { LiqpayPaymentCard } from "@/features/checkout/components/payment/liqpay-payment-card";
import { MonobankPaymentCard } from "@/features/checkout/components/payment/monobank-payment-card";
import { NovapayPaymentCard } from "@/features/checkout/components/payment/novapay-payment-card";
import type { CheckoutPaymentMethod } from "@/features/checkout/types/payment";

export function PaymentMethodToggle({
  value,
  onChange,
  labels,
}: {
  value: CheckoutPaymentMethod;
  onChange: (next: CheckoutPaymentMethod) => void;
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
  return (
    <div className="grid grid-cols-4 gap-3">
      <CodPaymentCard
        title={labels.codTitle}
        hint={labels.codHint}
        selected={value === "cash_on_delivery"}
        onSelect={() => onChange("cash_on_delivery")}
      />
      <MonobankPaymentCard
        title={labels.monobankTitle}
        hint={labels.monobankHint}
        selected={value === "monobank"}
        onSelect={() => onChange("monobank")}
      />
      <NovapayPaymentCard
        title={labels.novapayTitle}
        hint={labels.novapayHint}
        selected={value === "novapay"}
        onSelect={() => onChange("novapay")}
      />
      <LiqpayPaymentCard
        title={labels.liqpayTitle}
        hint={labels.liqpayHint}
        selected={value === "liqpay"}
        onSelect={() => onChange("liqpay")}
      />
    </div>
  );
}
