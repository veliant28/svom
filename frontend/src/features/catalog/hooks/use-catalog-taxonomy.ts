"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

import { getCategories } from "@/features/catalog/api/get-categories";
import type { CategorySummary } from "@/features/catalog/types";

type CatalogTaxonomyInitialData = {
  categories?: CategorySummary[];
};

export function useCatalogTaxonomy(initialData?: CatalogTaxonomyInitialData) {
  const locale = useLocale();
  const [categories, setCategories] = useState<CategorySummary[]>(initialData?.categories ?? []);

  useEffect(() => {
    let isMounted = true;

    async function loadTaxonomy() {
      try {
        const categoryData = await getCategories(locale);
        if (isMounted) {
          setCategories(categoryData);
        }
      } catch {
        if (isMounted) {
          setCategories([]);
        }
      }
    }

    void loadTaxonomy();

    return () => {
      isMounted = false;
    };
  }, [locale]);

  return { categories };
}
