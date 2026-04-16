"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";

import { getBrands } from "@/features/catalog/api/get-brands";
import { getCategories } from "@/features/catalog/api/get-categories";
import type { BrandSummary, CategorySummary } from "@/features/catalog/types";

export function useCatalogTaxonomy() {
  const locale = useLocale();
  const [brands, setBrands] = useState<BrandSummary[]>([]);
  const [categories, setCategories] = useState<CategorySummary[]>([]);

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
