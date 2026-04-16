"use client";

import { useTranslations } from "next-intl";

import { CatalogFiltersPanel } from "@/features/catalog/components/catalog-filters-panel";
import { CatalogGarageFitmentPanel } from "@/features/catalog/components/catalog-garage-fitment-panel";
import { CatalogTaxonomyPanel } from "@/features/catalog/components/catalog-taxonomy-panel";
import { useCatalogFilters } from "@/features/catalog/hooks/use-catalog-filters";
import { CatalogShowcaseSection } from "@/features/catalog/sections/catalog-showcase-section";

export function CatalogInteractiveSection() {
  const t = useTranslations("catalog");
  const { filters } = useCatalogFilters();

  return (
    <>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("subtitle")}
        </p>
      </section>

      <CatalogTaxonomyPanel />
      <CatalogFiltersPanel />
      <CatalogGarageFitmentPanel />
      <CatalogShowcaseSection filters={{ ...filters, pageSize: 16 }} />
    </>
  );
}
