import { useCallback } from "react";

import {
  getBackofficeAutoDbSupplierBrands,
  getBackofficeCatalogCategories,
  getBackofficeCatalogProducts,
} from "@/features/backoffice/api/catalog-api";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeCatalogBrand, BackofficeCatalogCategory, BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

type ProductsFiltersState = {
  q: string;
  isActiveFilter: string;
  supplierFilter: string;
  brandFilter: string;
  categoryFilter: string;
  page: number;
  pageSize: number;
};

export function useProductsPageData(filters: ProductsFiltersState, locale: string) {
  const productsQuery = useCallback(
    (token: string) =>
      getBackofficeCatalogProducts(token, {
        q: filters.q,
        is_active: filters.isActiveFilter,
        supplier: filters.supplierFilter,
        brand: filters.brandFilter,
        category: filters.categoryFilter,
        locale,
        page: filters.page,
        page_size: filters.pageSize,
      }),
    [
      filters.brandFilter,
      filters.categoryFilter,
      filters.isActiveFilter,
      filters.supplierFilter,
      filters.page,
      filters.pageSize,
      filters.q,
      locale,
    ],
  );

  const products = useBackofficeQuery<{ count: number; results: BackofficeCatalogProduct[] }>(productsQuery, [
    filters.q,
    filters.isActiveFilter,
    filters.supplierFilter,
    filters.brandFilter,
    filters.categoryFilter,
    filters.page,
    filters.pageSize,
    locale,
  ]);

  const brandsQuery = useCallback(async (authToken: string) => {
    const results: BackofficeCatalogBrand[] = [];
    let page = 1;

    while (true) {
      const chunk = await getBackofficeAutoDbSupplierBrands(authToken, { page, page_size: 500 });
      results.push(
        ...chunk.results.map((item) => ({
          id: String(item.id),
          name: item.name,
          slug: String(item.id),
          country: "",
          description: "",
          is_active: item.is_active,
          created_at: "",
          updated_at: "",
        })),
      );
      if (results.length >= chunk.count || chunk.results.length === 0) {
        break;
      }
      page += 1;
    }

    return { count: results.length, results };
  }, []);

  const categoriesQuery = useCallback(
    async (authToken: string) => {
      const results: BackofficeCatalogCategory[] = [];
      let page = 1;

      while (true) {
        const chunk = await getBackofficeCatalogCategories(authToken, { page, page_size: 500, locale });
        results.push(...chunk.results);
        if (results.length >= chunk.count || chunk.results.length === 0) {
          break;
        }
        page += 1;
      }

      return { count: results.length, results };
    },
    [locale],
  );

  const brands = useBackofficeQuery<{ count: number; results: BackofficeCatalogBrand[] }>(brandsQuery, []);
  const categories = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(categoriesQuery, [locale]);

  return {
    token: products.token,
    isLoading: products.isLoading,
    error: products.error,
    refetch: products.refetch,
    refetchBrands: brands.refetch,
    refetchCategories: categories.refetch,
    rows: products.data?.results ?? [],
    brands: brands.data?.results ?? [],
    rawCategories: categories.data?.results ?? [],
    productsCount: products.data?.count ?? 0,
  };
}
