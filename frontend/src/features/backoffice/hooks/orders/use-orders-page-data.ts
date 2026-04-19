import { useCallback, useMemo } from "react";

import { getBackofficeOrders } from "@/features/backoffice/api/orders-api";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

type OrdersFiltersState = {
  q: string;
  status: string;
  page: number;
};

export function useOrdersPageData(filters: OrdersFiltersState) {
  const ordersQuery = useCallback(
    (token: string) =>
      getBackofficeOrders(token, {
        q: filters.q,
        status: filters.status,
        page: filters.page,
      }),
    [filters.page, filters.q, filters.status],
  );

  const query = useBackofficeQuery<{ count: number; results: BackofficeOrderOperational[] }>(ordersQuery, [filters.q, filters.status, filters.page]);

  const rows = query.data?.results ?? [];
  const pagesCount = useMemo(() => Math.max(1, Math.ceil((query.data?.count ?? 0) / 20)), [query.data?.count]);
  const totalCount = query.data?.count ?? 0;

  return {
    ...query,
    rows,
    pagesCount,
    totalCount,
  };
}
