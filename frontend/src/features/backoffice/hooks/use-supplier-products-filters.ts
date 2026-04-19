import { useCallback, useState } from "react";

import { PAGE_SIZE_OPTIONS, type SupplierProductsPageSize } from "@/features/backoffice/lib/supplier-products/supplier-products-formatters";

export function useSupplierProductsFilters() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<SupplierProductsPageSize>(25);

  const onSearchChange = useCallback((value: string) => {
    setQ(value);
    setPage(1);
  }, []);

  const onPageSizeChange = useCallback((value: SupplierProductsPageSize) => {
    setPageSize(value);
    setPage(1);
  }, []);

  return {
    q,
    page,
    setPage,
    pageSize,
    pageSizeOptions: PAGE_SIZE_OPTIONS,
    onSearchChange,
    onPageSizeChange,
  };
}
