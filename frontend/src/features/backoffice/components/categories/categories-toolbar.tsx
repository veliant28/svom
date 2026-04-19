import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CategoriesToolbar({
  t,
  query,
  isActiveFilter,
  parentFilter,
  sortedParentOptions,
  getParentOptionLabel,
  onQueryChange,
  onIsActiveFilterChange,
  onParentFilterChange,
  onOpenCreate,
}: {
  t: Translator;
  query: string;
  isActiveFilter: string;
  parentFilter: string;
  sortedParentOptions: BackofficeCatalogCategory[];
  getParentOptionLabel: (category: BackofficeCatalogCategory) => string;
  onQueryChange: (value: string) => void;
  onIsActiveFilterChange: (value: string) => void;
  onParentFilterChange: (value: string) => void;
  onOpenCreate: () => void;
}) {
  return (
    <>
      <PageHeader title={t("categories.title")} />

      <section className="mb-3 flex flex-wrap items-center gap-2 lg:flex-nowrap">
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder={t("categories.filters.search")}
          className="h-9 min-w-[220px] flex-1 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={isActiveFilter}
          onChange={(event) => onIsActiveFilterChange(event.target.value)}
          className="h-9 w-[170px] shrink-0 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("categories.filters.all")}</option>
          <option value="true">{t("categories.filters.active")}</option>
          <option value="false">{t("categories.filters.inactive")}</option>
        </select>
        <select
          value={parentFilter}
          onChange={(event) => onParentFilterChange(event.target.value)}
          className="h-9 min-w-[220px] flex-1 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("categories.filters.anyParent")}</option>
          <option value="root">{t("categories.filters.rootOnly")}</option>
          {sortedParentOptions.map((item) => (
            <option key={item.id} value={item.id}>{getParentOptionLabel(item)}</option>
          ))}
        </select>
        <button
          type="button"
          className="h-9 shrink-0 rounded-md border px-3 text-xs font-semibold"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={onOpenCreate}
        >
          {t("categories.actions.create")}
        </button>
      </section>
    </>
  );
}
