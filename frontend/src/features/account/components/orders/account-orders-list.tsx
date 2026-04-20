"use client";

import { useLocale, useTranslations } from "next-intl";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { Order } from "@/features/commerce/types";
import { formatDateTime, formatMoney, resolveOrderStatusChipTone } from "@/features/account/lib/account-formatters";
import { Link } from "@/i18n/navigation";

type AccountOrdersListProps = {
  orders: Order[];
  isLoading: boolean;
};

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
        const tone = resolveOrderStatusChipTone(order.status);
        const statusLabel = t(`status.${order.status}`);

        return (
          <Link
            key={order.id}
            href={`/account/orders/${order.id}`}
            className="block rounded-xl border p-4 transition hover:opacity-95"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <article className="grid gap-3 sm:grid-cols-[minmax(12rem,1fr)_7.25rem_9.5rem_8.5rem] sm:items-center">
              <div className="min-w-0">
                <p className="truncate text-base font-semibold">{order.order_number}</p>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {formatDateTime(order.placed_at, locale)}
                </p>
              </div>

              <p className="text-sm leading-[1.05]" style={{ color: "var(--muted)" }}>
                {t("labels.items", { count: order.items.length })}
              </p>

              <p className="text-base font-semibold leading-[1.05]">{formatMoney(order.total, order.currency, locale)}</p>

              <div className="sm:justify-self-start">
                <BackofficeStatusChip tone={tone} className="whitespace-nowrap">{statusLabel}</BackofficeStatusChip>
              </div>
            </article>
          </Link>
        );
      })}
    </div>
  );
}
