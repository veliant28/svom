import { useCallback, useState } from "react";

export const ORDERS_PAGE_SIZE_OPTIONS = [15, 25, 50, 100] as const;
export type OrderPageSize = (typeof ORDERS_PAGE_SIZE_OPTIONS)[number];

export function useOrderFilters() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<OrderPageSize>(15);

  const onSearchChange = useCallback((value: string) => {
    setQ(value);
    setPage(1);
  }, []);

  const onStatusChange = useCallback((value: string) => {
    setStatus(value);
    setPage(1);
  }, []);

  const onPageSizeChange = useCallback((value: OrderPageSize) => {
    setPageSize(value);
    setPage(1);
  }, []);

  return {
    q,
    status,
    page,
    pageSize,
    pageSizeOptions: ORDERS_PAGE_SIZE_OPTIONS,
    setPage,
    onSearchChange,
    onStatusChange,
    onPageSizeChange,
  };
}
