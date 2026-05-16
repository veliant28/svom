"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { getAutoDbMatchingJobs, getAutoDbTecdocBatchState, runAutoDbTecdocBatch } from "@/features/backoffice/api/backoffice-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
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
};

export function AutoDbMatchingProductsTab({
  onSearchProduct,
  refreshNonce,
}: {
  onSearchProduct: (job: AutoDbProductJob) => void;
  refreshNonce: number;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();
  const [filters, setFilters] = useState<AutoDbMatchingProductsFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<AutoDbMatchingProductsPageSize>(25);
  const [batchSize, setBatchSize] = useState(200);
  const [isBatchSubmitting, setIsBatchSubmitting] = useState(false);
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
    return payload;
  }, [filters, page, pageSize]);

  const jobsQueryFn = useCallback((token: string) => getAutoDbMatchingJobs(token, params), [params]);
  const { token, data, isLoading, error, refetch } = useBackofficeQuery<AutoDbJobsResponse>(jobsQueryFn, [params]);
  const batchStateQueryFn = useCallback((apiToken: string) => getAutoDbTecdocBatchState(apiToken), []);
  const { data: batchState, refetch: refetchBatchState } = useBackofficeQuery(batchStateQueryFn, [refreshNonce]);

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refetch();
    void refetchBatchState();
  }, [refreshNonce, refetch, refetchBatchState]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refetchBatchState();
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [refetchBatchState]);

  const runTecdocBatch = useCallback(async () => {
    if (!token) return;
    setIsBatchSubmitting(true);
    try {
      const response = await runAutoDbTecdocBatch(token, { batch_size: batchSize });
      if (response.status === "already_running") {
        showWarning(t("toasts.batchAlreadyRunning"));
      } else {
        showSuccess(t("toasts.batchQueued"));
      }
      await Promise.all([refetchBatchState(), refetch()]);
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    } finally {
      setIsBatchSubmitting(false);
    }
  }, [batchSize, refetch, refetchBatchState, showApiError, showSuccess, showWarning, t, token]);

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

  const isTecdocBatchRunning = Boolean(batchState?.running);

  return (
    <>
      <AutoDbMatchingProductsFilters
        t={t}
        filters={filters}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onFilterChange={onFilterChange}
        onPageSizeChange={onPageSizeChange}
        batchSize={batchSize}
        onBatchSizeChange={setBatchSize}
        onRunTecdocBatch={() => void runTecdocBatch()}
        isTecdocBatchRunning={isTecdocBatchRunning}
        isBatchSubmitting={isBatchSubmitting}
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
