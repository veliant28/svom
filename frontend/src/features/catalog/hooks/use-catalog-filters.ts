"use client";

import { useSearchParams } from "next/navigation";

import { usePathname, useRouter } from "@/i18n/navigation";
import { buildCatalogFiltersQuery, parseCatalogFilters } from "@/features/catalog/lib/filter-params";
import type { CatalogFilters } from "@/features/catalog/types";

export function useCatalogFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const filters = parseCatalogFilters(new URLSearchParams(searchParams.toString()));

  const setFilters = (patch: Partial<CatalogFilters>) => {
    const nextFilters: CatalogFilters = { ...filters, ...patch };
    const nextParams = buildCatalogFiltersQuery(nextFilters);
    const query = nextParams.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  };

  const clearFilters = () => {
    router.replace(pathname);
  };

  return { filters, setFilters, clearFilters };
}
