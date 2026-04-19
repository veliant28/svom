import { useMemo } from "react";

import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { createProductColumns } from "@/features/backoffice/lib/products/product-columns";
import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductsTable({
  t,
  tUtr,
  tGpl,
  locale,
  rows,
  isLoading,
  error,
  selectedSet,
  allPageSelected,
  somePageSelected,
  deletingId,
  page,
  pagesCount,
  totalCount,
  onToggleSelectAllPage,
  onToggleSelected,
  onOpenEdit,
  onRequestDelete,
  onPageChange,
}: {
  t: Translator;
  tUtr: Translator;
  tGpl: Translator;
  locale: string;
  rows: BackofficeCatalogProduct[];
  isLoading: boolean;
  error: string | null;
  selectedSet: Set<string>;
  allPageSelected: boolean;
  somePageSelected: boolean;
  deletingId: string | null;
  page: number;
  pagesCount: number;
  totalCount: number;
  onToggleSelectAllPage: () => void;
  onToggleSelected: (id: string) => void;
  onOpenEdit: (item: BackofficeCatalogProduct) => void;
  onRequestDelete: (item: BackofficeCatalogProduct) => void;
  onPageChange: (next: number) => void;
}) {
  const columns = useMemo(
    () => createProductColumns({
      t,
      tUtr,
      tGpl,
      locale,
      selectedSet,
      allPageSelected,
      somePageSelected,
      onToggleSelectAllPage,
      onToggleSelected,
      onOpenEdit,
      onRequestDelete,
      deletingId,
    }),
    [
      allPageSelected,
      deletingId,
      locale,
      onOpenEdit,
      onRequestDelete,
      onToggleSelectAllPage,
      onToggleSelected,
      selectedSet,
      somePageSelected,
      t,
      tGpl,
      tUtr,
    ],
  );

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("products.states.empty")}>
      <BackofficeTable
        noHorizontalScroll
        emptyLabel={t("products.states.empty")}
        rows={rows}
        columns={columns}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("products.pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t("products.pagination.prev")}
          </button>
          <span>{t("products.pagination.page", { current: page, total: pagesCount })}</span>
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page >= pagesCount}
            onClick={() => onPageChange(Math.min(pagesCount, page + 1))}
          >
            {t("products.pagination.next")}
          </button>
        </div>
      </div>
    </AsyncState>
  );
}
