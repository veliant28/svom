import type { RefObject } from "react";
import type { OrderPageSize } from "@/features/backoffice/hooks/use-order-filters";

import { OrderBulkActions } from "./order-bulk-actions";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrdersFilters({
  t,
  q,
  status,
  pageSize,
  pageSizeOptions,
  onSearchChange,
  onStatusChange,
  onPageSizeChange,
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  bulkRunning,
  onToggleBulkActions,
  onBulkDelete,
}: {
  t: Translator;
  q: string;
  status: string;
  pageSize: OrderPageSize;
  pageSizeOptions: readonly OrderPageSize[];
  onSearchChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onPageSizeChange: (value: OrderPageSize) => void;
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  bulkRunning: boolean;
  onToggleBulkActions: () => void;
  onBulkDelete: () => void;
}) {
  return (
    <section className="mb-3 flex items-center gap-2">
      <OrderBulkActions
        bulkActionsRef={bulkActionsRef}
        bulkActionsOpen={bulkActionsOpen}
        selectedCount={selectedCount}
        running={bulkRunning}
        onToggle={onToggleBulkActions}
        onDelete={onBulkDelete}
        t={t}
      />

      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
        <input
          value={q}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t("orders.filters.search")}
          className="h-10 w-[220px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />

        <select
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number(event.target.value) as OrderPageSize)}
          className="h-10 rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {pageSizeOptions.map((sizeOption) => (
            <option key={sizeOption} value={sizeOption}>
              {`${t("orders.pagination.perPage")}: ${sizeOption}`}
            </option>
          ))}
        </select>

        <select
          value={status}
          onChange={(event) => onStatusChange(event.target.value)}
          className="h-10 w-[132px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("orders.filters.allStatuses")}</option>
          <option value="new">{t("statuses.new")}</option>
          <option value="processing">{t("statuses.processing")}</option>
          <option value="ready_for_shipment">{t("statuses.ready_for_shipment")}</option>
          <option value="shipped">{t("statuses.shipped")}</option>
          <option value="completed">{t("statuses.completed")}</option>
          <option value="cancelled">{t("statuses.cancelled")}</option>
        </select>
      </div>
    </section>
  );
}
