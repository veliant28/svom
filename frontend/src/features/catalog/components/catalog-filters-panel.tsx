"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useCatalogTaxonomy } from "@/features/catalog/hooks/use-catalog-taxonomy";
import { useCatalogFilters } from "@/features/catalog/hooks/use-catalog-filters";

export function CatalogFiltersPanel() {
  const t = useTranslations("catalog.filters");
  const { brands, categories } = useCatalogTaxonomy();
  const { filters, setFilters, clearFilters } = useCatalogFilters();

  const [queryInput, setQueryInput] = useState(filters.q ?? "");

  useEffect(() => {
    setQueryInput(filters.q ?? "");
  }, [filters.q]);

  return (
    <section className="mx-auto max-w-6xl px-4 py-3">
      <form
        className="grid gap-3 rounded-xl border p-4 md:grid-cols-2 lg:grid-cols-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onSubmit={(event) => {
          event.preventDefault();
          setFilters({ q: queryInput || undefined });
        }}
      >
        <label className="flex flex-col gap-1 text-xs">
          {t("query.label")}
          <input
            type="text"
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            placeholder={t("query.placeholder")}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("brand.label")}
          <select
            value={filters.brand ?? ""}
            onChange={(event) => setFilters({ brand: event.target.value || undefined })}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">{t("brand.all")}</option>
            {brands.map((brand) => (
              <option key={brand.id} value={brand.slug}>
                {brand.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          {t("category.label")}
          <select
            value={filters.category ?? ""}
            onChange={(event) => setFilters({ category: event.target.value || undefined })}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">{t("category.all")}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.slug}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("minPrice")}
            <input
              type="number"
              min="0"
              value={filters.min_price ?? ""}
              onChange={(event) => setFilters({ min_price: event.target.value || undefined })}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("maxPrice")}
            <input
              type="number"
              min="0"
              value={filters.max_price ?? ""}
              onChange={(event) => setFilters({ max_price: event.target.value || undefined })}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
          </label>
        </div>

        <label className="inline-flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={filters.is_featured === true}
            onChange={(event) => setFilters({ is_featured: event.target.checked ? true : undefined })}
          />
          {t("flags.featured")}
        </label>

        <label className="inline-flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={filters.is_new === true}
            onChange={(event) => setFilters({ is_new: event.target.checked ? true : undefined })}
          />
          {t("flags.new")}
        </label>

        <label className="inline-flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={filters.is_bestseller === true}
            onChange={(event) => setFilters({ is_bestseller: event.target.checked ? true : undefined })}
          />
          {t("flags.bestseller")}
        </label>

        <div className="flex items-end justify-end gap-2">
          <button
            type="submit"
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {t("actions.apply")}
          </button>
          <button
            type="button"
            onClick={clearFilters}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {t("actions.reset")}
          </button>
        </div>
      </form>
    </section>
  );
}
