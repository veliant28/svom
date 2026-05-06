"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

import { getBrands } from "@/features/catalog/api/get-brands";
import { getCategories } from "@/features/catalog/api/get-categories";
import type { BrandSummary, CategorySummary } from "@/features/catalog/types";

type CatalogTaxonomyInitialData = {
  brands?: BrandSummary[];
  categories?: CategorySummary[];
};

export function useCatalogTaxonomy(initialData?: CatalogTaxonomyInitialData) {
  const locale = useLocale();
  const [brands, setBrands] = useState<BrandSummary[]>(initialData?.brands ?? []);
  const [categories, setCategories] = useState<CategorySummary[]>(initialData?.categories ?? []);

  useEffect(() => {
    let isMounted = true;

    async function loadTaxonomy() {
      try {
        const [brandData, categoryData] = await Promise.all([getBrands(), getCategories(locale)]);
        if (isMounted) {
          setBrands(brandData);
          setCategories(categoryData);
        }
      } catch {
        if (isMounted) {
          setBrands([]);
          setCategories([]);
        }
      }
    }

    void loadTaxonomy();

    return () => {
      isMounted = false;
    };
  }, [locale]);

  return { brands, categories };
}
