import { RefreshCw } from "lucide-react";

import { OrderMonobankServiceInfo } from "@/features/backoffice/components/orders/payment/order-monobank-service-info";
import type { BackofficeOrderPayment } from "@/features/backoffice/types/orders.types";

export function OrderPaymentSection({
  payment,
  t,
  onRefresh,
  isRefreshing,
}: {
  payment: BackofficeOrderPayment | null | undefined;
  t: (key: string, values?: Record<string, string | number>) => string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}) {
  if (!payment) {
    return null;
  }

  const isMonobank = payment.provider === "monobank";

  return (
    <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{t("orders.payment.title")}</p>
        {onRefresh ? (
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onRefresh}
            aria-label={t("orders.payment.refreshStatus")}
            disabled={Boolean(isRefreshing)}
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
          </button>
        ) : null}
      </div>

      <div className="mt-2 grid gap-2 text-xs">
        <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.provider")}: </span>{payment.provider || "-"}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.method")}: </span>{payment.method || "-"}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.status")}: </span>{payment.status || "-"}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.amount")}: </span>{payment.amount} {payment.currency}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.lastWebhookAt")}: </span>{payment.last_webhook_received_at || "-"}</p>
        <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.lastSyncAt")}: </span>{payment.last_sync_at || "-"}</p>
      </div>

      {isMonobank ? (
        <div className="mt-3 rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <OrderMonobankServiceInfo payment={payment} t={t} />
        </div>
      ) : null}
    </section>
  );
}
