import { useMemo } from "react";

import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { supplierProductsEmptyLabel } from "@/features/backoffice/components/supplier-products/supplier-products-empty-state";
import { createSupplierProductsColumns } from "@/features/backoffice/lib/supplier-products/supplier-products-columns";
import type { BackofficeRawOffer } from "@/features/backoffice/types/imports.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierProductsTable({
  t,
  tUtr,
  tGpl,
  rows,
  isLoading,
  error,
  totalCount,
  page,
  pagesCount,
  isCategoryMappingOpen,
  selectedRawOfferId,
  onOpenCategoryMapping,
  onPageChange,
}: {
  t: Translator;
  tUtr: Translator;
  tGpl: Translator;
  rows: BackofficeRawOffer[];
  isLoading: boolean;
  error: string | null;
  totalCount: number;
  page: number;
  pagesCount: number;
  isCategoryMappingOpen: boolean;
  selectedRawOfferId: string | null;
  onOpenCategoryMapping: (rawOfferId: string) => void;
  onPageChange: (next: number) => void;
}) {
  const emptyLabel = supplierProductsEmptyLabel(t);

  const columns = useMemo(
    () => createSupplierProductsColumns({
      t,
      tUtr,
      tGpl,
      onOpenCategoryMapping,
      isCategoryMappingOpen,
      selectedRawOfferId,
    }),
    [isCategoryMappingOpen, onOpenCategoryMapping, selectedRawOfferId, t, tGpl, tUtr],
  );

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={emptyLabel}>
      <BackofficeTable
        noHorizontalScroll
        emptyLabel={emptyLabel}
        rows={rows}
        columns={columns}
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("productsPage.pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t("productsPage.pagination.prev")}
          </button>
          <span>{t("productsPage.pagination.page", { current: page, total: pagesCount })}</span>
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page >= pagesCount}
            onClick={() => onPageChange(Math.min(pagesCount, page + 1))}
          >
            {t("productsPage.pagination.next")}
          </button>
        </div>
      </div>
    </AsyncState>
  );
}
