"use client";

import { useEffect, useMemo } from "react";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { CatalogTaxonomyPanel } from "@/features/catalog/components/catalog-taxonomy-panel";
import { useCatalogFilters } from "@/features/catalog/hooks/use-catalog-filters";
import { useCatalogTaxonomy } from "@/features/catalog/hooks/use-catalog-taxonomy";
import { CatalogShowcaseSection } from "@/features/catalog/sections/catalog-showcase-section";

export function CatalogInteractiveSection() {
  const t = useTranslations("catalog");
  const { filters, setFilters } = useCatalogFilters();
  const { brands, categories } = useCatalogTaxonomy();
  const currentCategoryLabel = useMemo(() => {
    const categoryId = filters.category_id?.trim();
    const categorySlug = filters.category?.trim();
    const currentCategory = categoryId
      ? categories.find((category) => category.id === categoryId)
      : categorySlug
        ? categories.find((category) => category.slug === categorySlug)
        : null;

    if (!categoryId && !categorySlug) {
      return t("title");
    }

    if (currentCategory?.name) {
      return currentCategory.name;
    }

    return (categorySlug || categoryId || "")
      .replace(/[-_]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }, [categories, filters.category, filters.category_id, t]);

  useEffect(() => {
    if (filters.category_id || !filters.category) {
      return;
    }
    const matchedCategory = categories.find((category) => category.slug === filters.category);
    if (!matchedCategory) {
      return;
    }
    setFilters({
      category_id: matchedCategory.id,
      category: undefined,
    });
  }, [categories, filters.category, filters.category_id, setFilters]);

  return (
    <>
      <section className="mx-auto max-w-6xl px-4 pb-4 pt-8">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <span
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border text-[#fff7ef]"
            style={{ borderColor: "#d27a24", backgroundColor: "#e18a34" }}
            aria-hidden="true"
          >
            <ArrowRight size={13} strokeWidth={1.9} />
          </span>
          <p className="text-base font-semibold" style={{ color: "var(--muted)" }}>
            {currentCategoryLabel}
          </p>
        </div>
      </section>

      <CatalogShowcaseSection filters={filters} showHeading={false} />
      <CatalogTaxonomyPanel brands={brands} categories={categories} />
    </>
  );
}
