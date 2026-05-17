"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getAutoDbMatchingRemoteQuota,
  getAutoDbTecdocBatchState,
  runAutoDbTecdocBatch,
  stopAutoDbTecdocBatch,
} from "@/features/backoffice/api/backoffice-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type {
  AutoDbRemoteQuota,
  AutoDbTecdocBatchRun,
  AutoDbTecdocBatchStateResponse,
} from "@/features/backoffice/types/backoffice";

function clampBatchSize(value: number): number {
  const normalized = Number.isFinite(value) ? Math.round(value) : 200;
  return Math.max(10, Math.min(1000, normalized));
}

function toCount(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function useAutoDbBatchMonitor({
  refreshNonce,
  isHistoryModalOpen,
}: {
  refreshNonce: number;
  isHistoryModalOpen: boolean;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showApiError, showInfo, showSuccess, showWarning } = useBackofficeFeedback();
  const [batchSize, setBatchSize] = useState(200);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const batchStateQueryFn = useCallback((apiToken: string) => getAutoDbTecdocBatchState(apiToken), []);
  const { token, data: batchState, isLoading: isBatchStateLoading, refetch: refetchBatchState } = useBackofficeQuery<AutoDbTecdocBatchStateResponse>(
    batchStateQueryFn,
    [refreshNonce],
  );

  const quotaQueryFn = useCallback((apiToken: string) => getAutoDbMatchingRemoteQuota(apiToken), []);
  const { data: remoteQuota, isLoading: isQuotaLoading, refetch: refetchRemoteQuota } = useBackofficeQuery<AutoDbRemoteQuota>(
    quotaQueryFn,
    [refreshNonce],
  );

  const refreshBatch = useCallback(async () => {
    await Promise.all([refetchBatchState(), refetchRemoteQuota()]);
  }, [refetchBatchState, refetchRemoteQuota]);

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refreshBatch();
  }, [refreshBatch, refreshNonce]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refreshBatch();
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [refreshBatch]);

  const run = useMemo<AutoDbTecdocBatchRun | null>(() => {
    if (batchState?.active_run) {
      return batchState.active_run;
    }
    return batchState?.latest_run ?? null;
  }, [batchState?.active_run, batchState?.latest_run]);

  const isRunning = Boolean(batchState?.running);
  const isQuotaCooldownActive = remoteQuota?.status === "quota_paused";

  const runBatch = useCallback(async () => {
    if (!token) {
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await runAutoDbTecdocBatch(token, { batch_size: clampBatchSize(batchSize) });
      if (response.status === "already_running") {
        showWarning(t("toasts.batchAlreadyRunning"));
      } else {
        showSuccess(t("toasts.batchQueued"));
      }
      await refreshBatch();
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    } finally {
      setIsSubmitting(false);
    }
  }, [batchSize, refreshBatch, showApiError, showSuccess, showWarning, t, token]);

  const stopBatch = useCallback(async () => {
    if (!token) {
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await stopAutoDbTecdocBatch(token);
      if (response.status === "no_active_run") {
        showWarning(t("toasts.batchNoActiveRun"));
      } else {
        showSuccess(t("toasts.batchStopped"));
      }
      await refreshBatch();
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    } finally {
      setIsSubmitting(false);
    }
  }, [refreshBatch, showApiError, showSuccess, showWarning, t, token]);

  const previousRunningRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (!isHistoryModalOpen) {
      previousRunningRef.current = null;
    }
  }, [isHistoryModalOpen]);

  useEffect(() => {
    if (!isHistoryModalOpen) {
      return;
    }

    const previous = previousRunningRef.current;
    const current = Boolean(batchState?.running);

    if (previous === null) {
      previousRunningRef.current = current;
      return;
    }

    if (previous === current) {
      return;
    }

    previousRunningRef.current = current;

    if (!previous && current) {
      showInfo(t("toasts.batchStateRunning"));
      return;
    }

    const summary = run?.summary ?? {};
    const failed = toCount(summary.failed);
    const stopReason = String(summary.stopped_reason || "").trim();

    if (stopReason === "manual_stop") {
      showWarning(t("toasts.batchStateStopped"));
      return;
    }

    if (failed > 0) {
      showWarning(t("toasts.batchStateCompletedWithIssues", { count: failed }));
      return;
    }

    showSuccess(t("toasts.batchStateCompleted"));
  }, [batchState?.running, isHistoryModalOpen, run?.summary, showInfo, showSuccess, showWarning, t]);

  return {
    token,
    run,
    batchState,
    remoteQuota,
    isRunning,
    isQuotaCooldownActive,
    isLoading: isBatchStateLoading || isQuotaLoading,
    isSubmitting,
    batchSize,
    setBatchSize: (value: number) => setBatchSize(clampBatchSize(value)),
    refreshBatch,
    runBatch,
    stopBatch,
  };
}
