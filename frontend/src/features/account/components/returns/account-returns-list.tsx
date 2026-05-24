"use client";

import { useLocale, useTranslations } from "next-intl";
import { ScanBarcode, ScanLine } from "lucide-react";

import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { ReturnStatusChip } from "@/features/backoffice/components/widgets/return-status-chip";
import { formatReturnDate, formatReturnMoney } from "@/features/account/lib/returns-formatters";
import type { ReturnRequestListItem } from "@/features/commerce/types";
import { Link } from "@/i18n/navigation";

type AccountReturnsListProps = {
  items: ReturnRequestListItem[];
  isLoading: boolean;
};

export function AccountReturnsList({ items, isLoading }: AccountReturnsListProps) {
  const t = useTranslations("commerce.returns");
  const locale = useLocale();

  if (isLoading) {
    return <p className="text-sm" style={{ color: "var(--muted)" }}>{t("states.loading")}</p>;
  }

  if (!items.length) {
    return <p className="text-sm" style={{ color: "var(--muted)" }}>{t("states.empty")}</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <Link
          key={item.id}
          href={`/account/returns/${item.id}`}
          className="block rounded-xl border p-4 transition hover:opacity-95"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <article className="grid gap-3 sm:grid-cols-[minmax(12rem,1fr)_7.25rem_10.5rem_8rem_8.5rem] sm:items-center">
            <div className="min-w-0">
              <p className="truncate text-base font-semibold">
                {item.return_number}
                <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>
                  {formatReturnDate(item.created_at, locale)}
                </span>
              </p>
              <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{item.order_number}</p>
            </div>

            <p className="text-sm leading-[1.05]" style={{ color: "var(--muted)" }}>
              {item.return_day_label}
            </p>

            <div className="sm:justify-self-start">
              {item.tracking_number ? (
                <StatusChip tone="success" icon={ScanBarcode} className="whitespace-nowrap">
                  {item.tracking_number}
                </StatusChip>
              ) : (
                <StatusChip tone="orange" icon={ScanLine} className="whitespace-nowrap">
                  {t("labels.noTtn")}
                </StatusChip>
              )}
            </div>

            <p className="text-base font-semibold leading-[1.05]">{formatReturnMoney(item.refund_amount, locale)}</p>

            <div className="sm:justify-self-start">
              <ReturnStatusChip status={item.status} className="whitespace-nowrap" />
            </div>
          </article>
        </Link>
      ))}
    </div>
  );
}
