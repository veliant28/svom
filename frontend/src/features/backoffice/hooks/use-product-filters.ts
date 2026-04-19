import { useCallback, useState } from "react";

export const PRODUCTS_PAGE_SIZE_OPTIONS = [15, 25, 50, 100, 500] as const;
export type ProductPageSize = (typeof PRODUCTS_PAGE_SIZE_OPTIONS)[number];

export function useProductFilters() {
  const [q, setQ] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [brandFilter, setBrandFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<ProductPageSize>(25);

  const onSearchChange = useCallback((value: string) => {
    setQ(value);
    setPage(1);
  }, []);

  const onIsActiveFilterChange = useCallback((value: string) => {
    setIsActiveFilter(value);
    setPage(1);
  }, []);

  const onBrandFilterChange = useCallback((value: string) => {
    setBrandFilter(value);
    setPage(1);
  }, []);

  const onCategoryFilterChange = useCallback((value: string) => {
    setCategoryFilter(value);
    setPage(1);
  }, []);

  const onPageSizeChange = useCallback((value: ProductPageSize) => {
    setPageSize(value);
    setPage(1);
  }, []);

  return {
    q,
    isActiveFilter,
    brandFilter,
    categoryFilter,
    page,
    pageSize,
    pageSizeOptions: PRODUCTS_PAGE_SIZE_OPTIONS,
    setPage,
    onSearchChange,
    onIsActiveFilterChange,
    onBrandFilterChange,
    onCategoryFilterChange,
    onPageSizeChange,
  };
}
