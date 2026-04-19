import { useMemo } from "react";

import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { categoriesEmptyLabel } from "@/features/backoffice/components/categories/categories-empty-state";
import { createCategoryColumns } from "@/features/backoffice/lib/categories/category-columns";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CategoriesTable({
  t,
  locale,
  rows,
  isLoading,
  error,
  totalCount,
  page,
  pagesCount,
  deletingCategoryId,
  getDisplayName,
  getDisplayParentName,
  onEdit,
  onDelete,
  onPageChange,
}: {
  t: Translator;
  locale: string;
  rows: BackofficeCatalogCategory[];
  isLoading: boolean;
  error: string | null;
  totalCount: number;
  page: number;
  pagesCount: number;
  deletingCategoryId: string | null;
  getDisplayName: (category: BackofficeCatalogCategory, locale: string) => string;
  getDisplayParentName: (category: BackofficeCatalogCategory) => string;
  onEdit: (category: BackofficeCatalogCategory) => void;
  onDelete: (category: BackofficeCatalogCategory) => void;
  onPageChange: (next: number) => void;
}) {
  const emptyLabel = categoriesEmptyLabel(t);

  const columns = useMemo(
    () => createCategoryColumns({
      t,
      locale,
      deletingCategoryId,
      getDisplayName,
      getDisplayParentName,
      onEdit,
      onDelete,
    }),
    [deletingCategoryId, getDisplayName, getDisplayParentName, locale, onDelete, onEdit, t],
  );

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={emptyLabel}>
      <BackofficeTable
        emptyLabel={emptyLabel}
        rows={rows}
        columns={columns}
      />

      <div className="mt-3 flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("categories.pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t("categories.pagination.prev")}
          </button>
          <span>{t("categories.pagination.page", { current: page, total: pagesCount })}</span>
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page >= pagesCount}
            onClick={() => onPageChange(Math.min(pagesCount, page + 1))}
          >
            {t("categories.pagination.next")}
          </button>
        </div>
      </div>
    </AsyncState>
  );
}
