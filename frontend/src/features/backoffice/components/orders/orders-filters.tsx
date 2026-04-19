import type { RefObject } from "react";

import { OrderBulkActions } from "./order-bulk-actions";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrdersFilters({
  t,
  q,
  status,
  onSearchChange,
  onStatusChange,
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
  onSearchChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  bulkRunning: boolean;
  onToggleBulkActions: () => void;
  onBulkDelete: () => void;
}) {
  return (
    <section className="mb-3 flex flex-wrap items-center gap-2">
      <OrderBulkActions
        bulkActionsRef={bulkActionsRef}
        bulkActionsOpen={bulkActionsOpen}
        selectedCount={selectedCount}
        running={bulkRunning}
        onToggle={onToggleBulkActions}
        onDelete={onBulkDelete}
        t={t}
      />

      <input
        value={q}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder={t("orders.filters.search")}
        className="h-10 min-w-[260px] rounded-md border px-3 text-sm shrink-0"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      />

      <select
        value={status}
        onChange={(event) => onStatusChange(event.target.value)}
        className="h-10 rounded-md border px-3 text-sm shrink-0"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <option value="">{t("orders.filters.allStatuses")}</option>
        <option value="new">{t("statuses.new")}</option>
        <option value="confirmed">{t("statuses.confirmed")}</option>
        <option value="awaiting_procurement">{t("statuses.awaiting_procurement")}</option>
        <option value="reserved">{t("statuses.reserved")}</option>
        <option value="partially_reserved">{t("statuses.partially_reserved")}</option>
        <option value="ready_to_ship">{t("statuses.ready_to_ship")}</option>
        <option value="shipped">{t("statuses.shipped")}</option>
        <option value="completed">{t("statuses.completed")}</option>
        <option value="cancelled">{t("statuses.cancelled")}</option>
      </select>
    </section>
  );
}
