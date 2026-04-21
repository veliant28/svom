import type { RefObject } from "react";
import type { BackofficeCatalogBrand } from "@/features/backoffice/types/catalog.types";
import type { CategoryOption } from "@/features/backoffice/lib/products/product-form.types";
import type { ProductPageSize } from "@/features/backoffice/hooks/use-product-filters";

import { ProductBulkActions } from "./product-bulk-actions";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductsFilters({
  t,
  q,
  pageSize,
  pageSizeOptions,
  isActiveFilter,
  brandFilter,
  categoryFilter,
  brands,
  categories,
  onSearchChange,
  onPageSizeChange,
  onIsActiveFilterChange,
  onBrandFilterChange,
  onCategoryFilterChange,
  onCreate,
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  runningAction,
  onToggleBulkActions,
  onBulkMoveCategory,
  onBulkReindex,
  onBulkDelete,
}: {
  t: Translator;
  q: string;
  pageSize: ProductPageSize;
  pageSizeOptions: readonly ProductPageSize[];
  isActiveFilter: string;
  brandFilter: string;
  categoryFilter: string;
  brands: BackofficeCatalogBrand[];
  categories: CategoryOption[];
  onSearchChange: (value: string) => void;
  onPageSizeChange: (value: ProductPageSize) => void;
  onIsActiveFilterChange: (value: string) => void;
  onBrandFilterChange: (value: string) => void;
  onCategoryFilterChange: (value: string) => void;
  onCreate: () => void;
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  runningAction: "move_category" | "reindex" | "delete" | null;
  onToggleBulkActions: () => void;
  onBulkMoveCategory: () => void;
  onBulkReindex: () => void;
  onBulkDelete: () => void;
}) {
  return (
    <section className="mb-3 flex items-center gap-2">
      <ProductBulkActions
        bulkActionsRef={bulkActionsRef}
        bulkActionsOpen={bulkActionsOpen}
        selectedCount={selectedCount}
        runningAction={runningAction}
        onToggle={onToggleBulkActions}
        onOpenMoveCategoryModal={onBulkMoveCategory}
        onReindex={onBulkReindex}
        onOpenDeleteModal={onBulkDelete}
        t={t}
      />
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
        <input
          value={q}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t("products.filters.search")}
          className="h-10 w-[220px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number(event.target.value) as ProductPageSize)}
          className="h-10 rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {pageSizeOptions.map((sizeOption) => (
            <option key={sizeOption} value={sizeOption}>
              {`${t("products.pagination.perPage")}: ${sizeOption}`}
            </option>
          ))}
        </select>
        <select
          value={isActiveFilter}
          onChange={(event) => onIsActiveFilterChange(event.target.value)}
          className="h-10 w-[160px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("products.filters.allStates")}</option>
          <option value="true">{t("products.filters.active")}</option>
          <option value="false">{t("products.filters.inactive")}</option>
        </select>
        <select
          value={brandFilter}
          onChange={(event) => onBrandFilterChange(event.target.value)}
          className="h-10 w-[170px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("products.filters.allBrands")}</option>
          {brands.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
        <select
          value={categoryFilter}
          onChange={(event) => onCategoryFilterChange(event.target.value)}
          className="h-10 w-[180px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("products.filters.allCategories")}</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
      </div>
      <button
        type="button"
        className="h-10 rounded-md border px-3 text-sm font-semibold shrink-0"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onClick={onCreate}
      >
        {t("products.actions.create")}
      </button>
    </section>
  );
}
