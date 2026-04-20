import type { BackofficeOrderPayment } from "@/features/backoffice/types/orders.types";

export function OrderMonobankServiceInfo({
  payment,
  t,
}: {
  payment: BackofficeOrderPayment;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  return (
    <div className="grid gap-2 text-xs">
      <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.invoiceId")}: </span>{payment.invoice_id || "-"}</p>
      <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.reference")}: </span>{payment.reference || "-"}</p>
      <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.failureReason")}: </span>{payment.failure_reason || "-"}</p>
      {payment.page_url ? (
        <a
          href={payment.page_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex w-fit rounded-md border px-2 py-1 font-semibold"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        >
          {t("orders.payment.openPaymentPage")}
        </a>
      ) : null}
    </div>
  );
}
