import type { SupplierProductsPageSize } from "@/features/backoffice/lib/supplier-products/supplier-products-formatters";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierProductsFilters({
  t,
  tCommon,
  q,
  pageSize,
  pageSizeOptions,
  isPublishing,
  publishDisabled,
  onSearchChange,
  onPageSizeChange,
  onPublishMapped,
}: {
  t: Translator;
  tCommon: Translator;
  q: string;
  pageSize: SupplierProductsPageSize;
  pageSizeOptions: readonly SupplierProductsPageSize[];
  isPublishing: boolean;
  publishDisabled: boolean;
  onSearchChange: (value: string) => void;
  onPageSizeChange: (value: SupplierProductsPageSize) => void;
  onPublishMapped: () => void;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
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
