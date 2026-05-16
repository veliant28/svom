"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { getAutoDbMatchingJobs, getAutoDbMatchingRemoteQuota, getAutoDbTecdocBatchState, runAutoDbTecdocBatch, stopAutoDbTecdocBatch } from "@/features/backoffice/api/backoffice-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbJobsResponse, AutoDbProductJob, AutoDbRemoteQuota } from "@/features/backoffice/types/backoffice";

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

function resolveQuotaCooldownSeconds(quota: AutoDbRemoteQuota | null | undefined): number {
  if (!quota) {
    return 0;
  }
  if (quota.cooldown_until) {
    const cooldownTs = new Date(quota.cooldown_until).getTime();
    if (Number.isFinite(cooldownTs)) {
      return Math.max(0, Math.floor((cooldownTs - Date.now()) / 1000));
    }
  }
  if (quota.status === "quota_paused") {
    return Math.max(0, Math.floor(Number(quota.seconds_until_reset || 0)));
  }
  return 0;
}

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
  const [selectedSet, setSelectedSet] = useState<Set<string>>(new Set());
  const [bulkActionsOpen, setBulkActionsOpen] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement | null>(null);

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
  const remoteQuotaQueryFn = useCallback((apiToken: string) => getAutoDbMatchingRemoteQuota(apiToken), []);
  const { data: remoteQuota, refetch: refetchRemoteQuota } = useBackofficeQuery<AutoDbRemoteQuota>(remoteQuotaQueryFn, [refreshNonce]);

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refetch();
    void refetchBatchState();
    void refetchRemoteQuota();
  }, [refreshNonce, refetch, refetchBatchState, refetchRemoteQuota]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refetchBatchState();
      void refetchRemoteQuota();
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [refetchBatchState, refetchRemoteQuota]);

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

  const stopTecdocBatch = useCallback(async () => {
    if (!token) return;
    setIsBatchSubmitting(true);
    try {
      const response = await stopAutoDbTecdocBatch(token);
      if (response.status === "no_active_run") {
        showWarning(t("toasts.batchNoActiveRun"));
      } else {
        showSuccess(t("toasts.batchStopped"));
      }
      await Promise.all([refetchBatchState(), refetch()]);
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    } finally {
      setIsBatchSubmitting(false);
    }
  }, [refetch, refetchBatchState, showApiError, showSuccess, showWarning, t, token]);

  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const totalCount = data?.count ?? 0;
  const pagesCount = Math.max(1, Math.ceil(totalCount / pageSize));
  const rowIds = useMemo(() => rows.map((item) => String(item.id)), [rows]);
  const allPageSelected = rowIds.length > 0 && rowIds.every((id) => selectedSet.has(id));
  const somePageSelected = rowIds.some((id) => selectedSet.has(id));

  const onFilterChange = useCallback(<K extends keyof AutoDbMatchingProductsFilterState>(key: K, value: AutoDbMatchingProductsFilterState[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }, []);

  const onPageSizeChange = useCallback((value: AutoDbMatchingProductsPageSize) => {
    setPageSize(value);
    setPage(1);
  }, []);

  const toggleSelected = useCallback((id: string) => {
    const key = String(id);
    setSelectedSet((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const toggleSelectAllPage = useCallback(() => {
    if (!rowIds.length) return;
    setSelectedSet((prev) => {
      const next = new Set(prev);
      const allSelected = rowIds.every((id) => next.has(id));
      if (allSelected) {
        for (const id of rowIds) next.delete(id);
      } else {
        for (const id of rowIds) next.add(id);
      }
      return next;
    });
  }, [rowIds]);

  const runBulkBatch = useCallback(async () => {
    if (!token) return;
    const selectedIds = [...selectedSet];
    if (!selectedIds.length) {
      showWarning(t("toasts.bulkNothingSelected"));
      return;
    }
    setBulkActionsOpen(false);
    setIsBatchSubmitting(true);
    try {
      const response = await runAutoDbTecdocBatch(token, {
        batch_size: selectedIds.length,
        product_ids: selectedIds,
      });
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
  }, [refetch, refetchBatchState, selectedSet, showApiError, showSuccess, showWarning, t, token]);

  const isTecdocBatchRunning = Boolean(batchState?.running);
  const isQuotaCooldownActive = resolveQuotaCooldownSeconds(remoteQuota) > 0;

  useEffect(() => {
    if (!bulkActionsOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!bulkActionsRef.current) return;
      if (bulkActionsRef.current.contains(event.target as Node)) return;
      setBulkActionsOpen(false);
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setBulkActionsOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onEscape);
    };
  }, [bulkActionsOpen]);

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
        onStopTecdocBatch={() => void stopTecdocBatch()}
        isTecdocBatchRunning={isTecdocBatchRunning}
        isQuotaCooldownActive={isQuotaCooldownActive}
        isBatchSubmitting={isBatchSubmitting}
        bulkActionsRef={bulkActionsRef}
        bulkActionsOpen={bulkActionsOpen}
        selectedCount={selectedSet.size}
        isBulkRunning={isBatchSubmitting}
        onToggleBulkActions={() => setBulkActionsOpen((prev) => !prev)}
        onRunBulkBatch={() => void runBulkBatch()}
      />

      <AutoDbMatchingProductsTable
        t={t}
        rows={rows}
        isLoading={isLoading}
        error={error}
        page={page}
        pagesCount={pagesCount}
        totalCount={totalCount}
        selectedSet={selectedSet}
        allPageSelected={allPageSelected}
        somePageSelected={somePageSelected}
        onPageChange={setPage}
        onToggleSelectAllPage={toggleSelectAllPage}
        onToggleSelected={toggleSelected}
        onOpenDetails={(job) => setDrawerJobId(job.id)}
        onSearchProduct={onSearchProduct}
      />

      <AutoDbEvidenceDrawer jobId={drawerJobId} onClose={() => setDrawerJobId(null)} />
    </>
  );
}
