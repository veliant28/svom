"use client";

import { useLocale, useTranslations } from "next-intl";

import type { Order } from "@/features/commerce/types";
import { formatDateTime, formatMoney, resolveOrderStatusTone } from "@/features/account/lib/account-formatters";

type AccountOrdersListProps = {
  orders: Order[];
  isLoading: boolean;
};

function getStatusStyle(tone: ReturnType<typeof resolveOrderStatusTone>) {
  if (tone === "success") {
    return {
      borderColor: "var(--status-success-border)",
      backgroundColor: "var(--status-success-bg)",
      color: "var(--status-success-text)",
    };
  }
  if (tone === "warning") {
    return {
      borderColor: "var(--status-warning-border)",
      backgroundColor: "var(--status-warning-bg)",
      color: "var(--status-warning-text)",
    };
  }
  if (tone === "danger") {
    return {
      borderColor: "var(--status-error-border)",
      backgroundColor: "var(--status-error-bg)",
      color: "var(--status-error-text)",
    };
  }
  return {
    borderColor: "var(--border)",
    backgroundColor: "color-mix(in srgb, var(--surface-2) 60%, var(--surface))",
    color: "var(--text)",
  };
}

export function AccountOrdersList({ orders, isLoading }: AccountOrdersListProps) {
  const t = useTranslations("commerce.orders");
  const locale = useLocale();

  if (isLoading) {
    return (
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        {t("states.loading")}
      </p>
    );
  }

  if (orders.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        {t("states.empty")}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {orders.map((order) => {
        const tone = resolveOrderStatusTone(order.status);
        const statusLabel = t(`status.${order.status}`);

        return (
          <article
            key={order.id}
            className="rounded-xl border p-4"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-base font-semibold">{order.order_number}</p>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {formatDateTime(order.placed_at, locale)}
                </p>
              </div>
              <span className="inline-flex rounded-full border px-2 py-1 text-xs font-medium" style={getStatusStyle(tone)}>
                {statusLabel}
              </span>
            </div>

            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
              <p>{t("labels.items", { count: order.items.length })}</p>
              <p>{t("labels.client", { fullName: order.contact_full_name || "-" })}</p>
              <p className="font-semibold">{formatMoney(order.total, order.currency, locale)}</p>
            </div>

            {order.items.length > 0 ? (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full border-separate border-spacing-0 text-xs">
                  <thead>
                    <tr style={{ color: "var(--muted)" }}>
                      <th className="px-2 py-1 text-left font-medium">{t("table.sku")}</th>
                      <th className="px-2 py-1 text-left font-medium">{t("table.product")}</th>
                      <th className="px-2 py-1 text-right font-medium">{t("table.qty")}</th>
                      <th className="px-2 py-1 text-right font-medium">{t("table.total")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((item) => (
                      <tr key={item.id}>
                        <td className="px-2 py-1">{item.product_sku || "-"}</td>
                        <td className="px-2 py-1">{item.product_name}</td>
                        <td className="px-2 py-1 text-right">{item.quantity}</td>
                        <td className="px-2 py-1 text-right">{formatMoney(item.line_total, order.currency, locale)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
