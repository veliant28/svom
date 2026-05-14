import { surfaceStyle } from "./ui";

export type AutoDbMatchingProductsPageSize = 25 | 50 | 100;

export type AutoDbMatchingProductsFilterState = {
  q: string;
  supplier_code: "" | "gpl" | "utr";
  matching_status: string;
  tecdoc_status: "" | "tecdoc" | "non_tecdoc" | "unknown";
  flag: "" | "only_safe_candidates" | "needs_review" | "quota_paused" | "bad_article_source" | "split_needed" | "unsafe_ambiguous";
};

type Translator = (key: string, values?: Record<string, string | number>) => string;

const STATUS_OPTIONS = [
  "new",
  "local_found",
  "remote_found",
  "clone_synced",
  "safe_link_candidate",
  "needs_review",
  "quota_paused",
  "skipped_bad_article_source",
  "skipped_brand_unresolved",
  "skipped_non_tecdoc",
  "skipped_split_needed",
  "skipped_unsafe_ambiguous",
  "linked",
] as const;

function humanizeStatus(value: string): string {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  return raw.replaceAll("_", " ");
}

function safeTranslate(t: Translator, key: string, fallback: string): string {
  try {
    return t(key as never);
  } catch {
    return fallback;
  }
}

export function AutoDbMatchingProductsFilters({
  t,
  filters,
  pageSize,
  pageSizeOptions,
  onFilterChange,
  onPageSizeChange,
}: {
  t: Translator;
  filters: AutoDbMatchingProductsFilterState;
  pageSize: AutoDbMatchingProductsPageSize;
  pageSizeOptions: readonly AutoDbMatchingProductsPageSize[];
  onFilterChange: <K extends keyof AutoDbMatchingProductsFilterState>(key: K, value: AutoDbMatchingProductsFilterState[K]) => void;
  onPageSizeChange: (value: AutoDbMatchingProductsPageSize) => void;
}) {
  return (
    <section className="mb-3 flex items-center gap-2">
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto py-1">
        <input
          value={filters.q}
          onChange={(event) => onFilterChange("q", event.target.value)}
          placeholder={t("products.search")}
          className="h-10 w-[240px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
          style={surfaceStyle}
        />

        <select
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number(event.target.value) as AutoDbMatchingProductsPageSize)}
          className="h-10 rounded-md border px-3 text-sm shrink-0"
          style={surfaceStyle}
        >
          {pageSizeOptions.map((size) => (
            <option key={size} value={size}>
              {t("products.filters.perPage", { count: size })}
            </option>
          ))}
        </select>

        <select
          value={filters.supplier_code}
          onChange={(event) => onFilterChange("supplier_code", event.target.value as AutoDbMatchingProductsFilterState["supplier_code"])}
          className="h-10 w-[138px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("products.filters.allSuppliers")}</option>
          <option value="gpl">{t("products.filters.supplierGpl")}</option>
          <option value="utr">{t("products.filters.supplierUtr")}</option>
        </select>

        <select
          value={filters.matching_status}
          onChange={(event) => onFilterChange("matching_status", event.target.value)}
          className="h-10 w-[188px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("products.filters.allStatuses")}</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {safeTranslate(
                t,
                `status.matching.${status}`,
                safeTranslate(t, `status.matchingShort.${status}`, humanizeStatus(status)),
              )}
            </option>
          ))}
        </select>

        <select
          value={filters.tecdoc_status}
          onChange={(event) => onFilterChange("tecdoc_status", event.target.value as AutoDbMatchingProductsFilterState["tecdoc_status"])}
          className="h-10 w-[150px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("products.filters.allTecdoc")}</option>
          <option value="tecdoc">{t("filters.tecdocOnly")}</option>
          <option value="non_tecdoc">{t("filters.nonTecdocOnly")}</option>
          <option value="unknown">{t("filters.unknownReview")}</option>
        </select>

        <select
          value={filters.flag}
          onChange={(event) => onFilterChange("flag", event.target.value as AutoDbMatchingProductsFilterState["flag"])}
          className="h-10 w-[180px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("filters.all")}</option>
          <option value="only_safe_candidates">{t("filters.only_safe_candidates")}</option>
          <option value="needs_review">{t("filters.needs_review")}</option>
          <option value="quota_paused">{t("filters.quota_paused")}</option>
          <option value="bad_article_source">{t("filters.bad_article_source")}</option>
          <option value="split_needed">{t("filters.split_needed")}</option>
          <option value="unsafe_ambiguous">{t("filters.unsafe_ambiguous")}</option>
        </select>

      </div>

    </section>
  );
}
