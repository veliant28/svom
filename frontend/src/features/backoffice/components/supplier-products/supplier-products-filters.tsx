import type { SupplierProductsStatusFilter } from "@/features/backoffice/hooks/use-supplier-products-filters";
import type { SupplierProductsPageSize } from "@/features/backoffice/lib/supplier-products/supplier-products-formatters";
import type { RefObject } from "react";

import { SupplierProductsBulkActions } from "@/features/backoffice/components/supplier-products/supplier-products-bulk-actions";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierProductsFilters({
  t,
  tCommon,
  q,
  status,
  pageSize,
  pageSizeOptions,
  isPublishing,
  publishDisabled,
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  onSearchChange,
  onStatusChange,
  onPageSizeChange,
  onToggleBulkActions,
  onPublishSelected,
  onPublishMapped,
}: {
  t: Translator;
  tCommon: Translator;
  q: string;
  status: SupplierProductsStatusFilter;
  pageSize: SupplierProductsPageSize;
  pageSizeOptions: readonly SupplierProductsPageSize[];
  isPublishing: boolean;
  publishDisabled: boolean;
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: SupplierProductsStatusFilter) => void;
  onPageSizeChange: (value: SupplierProductsPageSize) => void;
  onToggleBulkActions: () => void;
  onPublishSelected: () => void;
  onPublishMapped: () => void;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <SupplierProductsBulkActions
        bulkActionsRef={bulkActionsRef}
        bulkActionsOpen={bulkActionsOpen}
        selectedCount={selectedCount}
        isPublishing={isPublishing}
        onToggle={onToggleBulkActions}
        onPublishSelected={onPublishSelected}
        t={t}
        tCommon={tCommon}
      />
      <input
        value={q}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder={t("productsPage.search")}
        className="h-10 min-w-[260px] rounded-md border px-3 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      />
      <select
        value={String(pageSize)}
        onChange={(event) => onPageSizeChange(Number(event.target.value) as SupplierProductsPageSize)}
        className="h-10 rounded-md border px-3 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        {pageSizeOptions.map((sizeOption) => (
          <option key={sizeOption} value={sizeOption}>
            {`${t("productsPage.pagination.perPage")}: ${sizeOption}`}
          </option>
        ))}
      </select>
      <select
        value={status}
        onChange={(event) => onStatusChange(event.target.value as SupplierProductsStatusFilter)}
        className="h-10 rounded-md border px-3 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <option value="all">{t("productsPage.filters.allStatuses")}</option>
        <option value="needs_review">{t("productsPage.review.statuses.needs_review")}</option>
        <option value="manual_mapped">{t("productsPage.review.statuses.manual_mapped")}</option>
        <option value="auto_mapped">{t("productsPage.review.statuses.auto_mapped")}</option>
        <option value="unmapped">{t("productsPage.review.statuses.unmapped")}</option>
      </select>
      <button
        type="button"
        className="h-10 rounded-md border px-3 text-sm font-semibold disabled:opacity-60"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        disabled={publishDisabled}
        onClick={onPublishMapped}
      >
        {isPublishing ? tCommon("loading") : t("productsPage.actions.publishMapped")}
      </button>
    </div>
  );
}
