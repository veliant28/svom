"use client";

import { useTranslations } from "next-intl";

import { useCatalogTaxonomy } from "@/features/catalog/hooks/use-catalog-taxonomy";

export function CatalogTaxonomyPanel() {
  const t = useTranslations("catalog");
  const { brands, categories } = useCatalogTaxonomy();

  return (
    <section className="mx-auto max-w-6xl px-4 py-3">
      <div className="grid gap-3 rounded-xl border p-4 md:grid-cols-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div>
          <h2 className="text-sm font-semibold">{t("taxonomy.brands")}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {brands.map((brand) => (
              <span key={brand.id} className="rounded-md border px-2 py-1 text-xs" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
                {brand.name}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-sm font-semibold">{t("taxonomy.categories")}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {categories.map((category) => (
              <span key={category.id} className="rounded-md border px-2 py-1 text-xs" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
                {category.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
