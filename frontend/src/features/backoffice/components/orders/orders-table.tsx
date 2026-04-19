import { useMemo } from "react";

import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { createOrderColumns } from "@/features/backoffice/lib/orders/order-columns";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrdersTable({
  t,
  locale,
  rows,
  isLoading,
  error,
  selectedSet,
  allPageSelected,
  somePageSelected,
  deletingId,
  openingId,
  waybillLoadingId,
  supplierLoadingId,
  page,
  pagesCount,
  totalCount,
  onToggleSelectAllPage,
  onToggleSelected,
  onOpen,
  onWaybill,
  onSupplierOrder,
  onDelete,
  onPageChange,
}: {
  t: Translator;
  locale: string;
  rows: BackofficeOrderOperational[];
  isLoading: boolean;
  error: string | null;
  selectedSet: Set<string>;
  allPageSelected: boolean;
  somePageSelected: boolean;
  deletingId: string | null;
  openingId: string | null;
  waybillLoadingId: string | null;
  supplierLoadingId: string | null;
  page: number;
  pagesCount: number;
  totalCount: number;
  onToggleSelectAllPage: () => void;
  onToggleSelected: (id: string) => void;
  onOpen: (item: BackofficeOrderOperational) => void;
  onWaybill: (item: BackofficeOrderOperational) => void;
  onSupplierOrder: (item: BackofficeOrderOperational) => void;
  onDelete: (item: BackofficeOrderOperational) => void;
  onPageChange: (next: number) => void;
}) {
  const columns = useMemo(
    () => createOrderColumns({
      t,
      locale,
      selectedSet,
      allPageSelected,
      somePageSelected,
      deletingId,
      openingId,
      waybillLoadingId,
      supplierLoadingId,
      onToggleSelectAllPage,
      onToggleSelected,
      onOpen,
      onWaybill,
      onSupplierOrder,
      onDelete,
    }),
    [
      allPageSelected,
      deletingId,
      locale,
      onDelete,
      onOpen,
      onSupplierOrder,
      onToggleSelectAllPage,
      onToggleSelected,
      onWaybill,
      openingId,
      selectedSet,
      somePageSelected,
      supplierLoadingId,
      t,
      waybillLoadingId,
    ],
  );

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("orders.states.empty")}>
      <BackofficeTable
        noHorizontalScroll
        emptyLabel={t("orders.states.empty")}
        rows={rows}
        columns={columns}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("orders.pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t("orders.pagination.prev")}
          </button>
          <span>{t("orders.pagination.page", { current: page, total: pagesCount })}</span>
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page >= pagesCount}
            onClick={() => onPageChange(Math.min(pagesCount, page + 1))}
          >
            {t("orders.pagination.next")}
          </button>
        </div>
      </div>
    </AsyncState>
  );
}
