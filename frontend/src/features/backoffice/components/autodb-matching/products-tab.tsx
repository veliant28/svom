"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { getAutoDbMatchingJobs } from "@/features/backoffice/api/backoffice-api";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbJobsResponse, AutoDbProductJob } from "@/features/backoffice/types/backoffice";

import { AutoDbEvidenceDrawer } from "./evidence-drawer";
import {
  AutoDbMatchingProductsFilters,
  type AutoDbMatchingProductsFilterState,
  type AutoDbMatchingProductsPageSize,
} from "./products-filters";
import { AutoDbMatchingProductsTable } from "./products-table";

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

const DEFAULT_FILTERS: AutoDbMatchingProductsFilterState = {
  q: "",
  supplier_code: "",
  matching_status: "",
  tecdoc_status: "",
  flag: "",
};

const FLAG_PARAM_MAP: Record<
  Exclude<AutoDbMatchingProductsFilterState["flag"], "">,
  "only_safe_candidates" | "needs_review" | "quota_paused" | "bad_article_source" | "split_needed" | "unsafe_ambiguous"
> = {
  only_safe_candidates: "only_safe_candidates",
  needs_review: "needs_review",
  quota_paused: "quota_paused",
  bad_article_source: "bad_article_source",
  split_needed: "split_needed",
  unsafe_ambiguous: "unsafe_ambiguous",
};

export function AutoDbMatchingProductsTab({
  onSearchProduct,
  refreshNonce,
}: {
  onSearchProduct: (job: AutoDbProductJob) => void;
  refreshNonce: number;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const [filters, setFilters] = useState<AutoDbMatchingProductsFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<AutoDbMatchingProductsPageSize>(25);
  const [drawerJobId, setDrawerJobId] = useState<string | null>(null);

  const params = useMemo(() => {
    const payload: Record<string, string | number | boolean> = {
      page,
      page_size: pageSize,
      ordering: "-updated_at",
    };
    const textFilters: Array<keyof Pick<AutoDbMatchingProductsFilterState, "q" | "supplier_code" | "matching_status" | "tecdoc_status">> = [
      "q",
      "supplier_code",
      "matching_status",
      "tecdoc_status",
    ];
    for (const key of textFilters) {
      const value = String(filters[key] || "").trim();
      if (value) {
        payload[key] = value;
      }
    }
    if (filters.flag) {
      payload[FLAG_PARAM_MAP[filters.flag]] = true;
    }
    return payload;
  }, [filters, page, pageSize]);

  const queryFn = useCallback((token: string) => getAutoDbMatchingJobs(token, params), [params]);
  const { data, isLoading, error, refetch } = useBackofficeQuery<AutoDbJobsResponse>(queryFn, [params]);

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refetch();
  }, [refreshNonce, refetch]);

  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const pagesCount = Math.max(1, Math.ceil(totalCount / pageSize));

  const onFilterChange = useCallback(<K extends keyof AutoDbMatchingProductsFilterState>(key: K, value: AutoDbMatchingProductsFilterState[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }, []);

  const onPageSizeChange = useCallback((value: AutoDbMatchingProductsPageSize) => {
    setPageSize(value);
    setPage(1);
  }, []);

  return (
    <>
      <AutoDbMatchingProductsFilters
        t={t}
        filters={filters}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onFilterChange={onFilterChange}
        onPageSizeChange={onPageSizeChange}
      />

      <AutoDbMatchingProductsTable
        t={t}
        rows={rows}
        isLoading={isLoading}
        error={error}
        page={page}
        pagesCount={pagesCount}
        totalCount={totalCount}
        onPageChange={setPage}
        onOpenDetails={(job) => setDrawerJobId(job.id)}
        onSearchProduct={onSearchProduct}
      />

      <AutoDbEvidenceDrawer jobId={drawerJobId} onClose={() => setDrawerJobId(null)} />
    </>
  );
}
