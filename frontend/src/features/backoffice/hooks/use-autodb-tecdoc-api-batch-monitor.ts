"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getAutoDbMatchingRemoteQuota,
  getAutoDbTecdocApiBatchState,
  runAutoDbTecdocApiBatch,
  stopAutoDbTecdocApiBatch,
} from "@/features/backoffice/api/backoffice-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type {
  AutoDbRemoteQuota,
  AutoDbTecdocBatchRun,
  AutoDbTecdocBatchStateResponse,
} from "@/features/backoffice/types/backoffice";

function clampBatchSize(value: number): number {
  const normalized = Number.isFinite(value) ? Math.round(value) : 50;
  return Math.max(10, Math.min(1000, normalized));
}

function toCount(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function useAutoDbTecdocApiBatchMonitor({
  refreshNonce,
  isHistoryModalOpen,
  enableToasts = true,
}: {
  refreshNonce: number;
  isHistoryModalOpen: boolean;
  enableToasts?: boolean;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showApiError, showInfo, showSuccess, showWarning } = useBackofficeFeedback();
  const [batchSize, setBatchSize] = useState(100);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const batchStateQueryFn = useCallback((apiToken: string) => getAutoDbTecdocApiBatchState(apiToken), []);
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
      const response = await runAutoDbTecdocApiBatch(token, { batch_size: clampBatchSize(batchSize), continuous: true });
      if (response.status === "already_running") {
        showWarning(t("toasts.tecdocApiAlreadyRunning"));
      } else {
        showSuccess(t("toasts.tecdocApiQueued"));
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
      const response = await stopAutoDbTecdocApiBatch(token);
      if (response.status === "no_active_run") {
        showWarning(t("toasts.tecdocApiNoActiveRun"));
      } else {
        showSuccess(t("toasts.tecdocApiStopped"));
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
    if (!enableToasts) {
      previousRunningRef.current = null;
      return;
    }
    if (!isHistoryModalOpen) {
      previousRunningRef.current = null;
    }
  }, [enableToasts, isHistoryModalOpen]);

  useEffect(() => {
    if (!enableToasts) {
      return;
    }
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
      showInfo(t("toasts.tecdocApiStateRunning"));
      return;
    }

    const summary = run?.summary ?? {};
    const failed = toCount(summary.failed);
    const stopReason = String(summary.stopped_reason || "").trim();

    if (stopReason === "manual_stop") {
      showWarning(t("toasts.tecdocApiStateStopped"));
      return;
    }

    if (failed > 0) {
      showWarning(t("toasts.tecdocApiStateCompletedWithIssues", { count: failed }));
      return;
    }

    showSuccess(t("toasts.tecdocApiStateCompleted"));
  }, [batchState?.running, enableToasts, isHistoryModalOpen, run?.summary, showInfo, showSuccess, showWarning, t]);

  const previousCountersRef = useRef<{ runId: string; cycleIndex: number; linked: number; failed: number } | null>(null);
  useEffect(() => {
    if (!enableToasts) {
      previousCountersRef.current = null;
      return;
    }
    if (!run) {
      previousCountersRef.current = null;
      return;
    }

    const summary = run.summary ?? {};
    const cycleIndex = Math.max(toCount(summary.cycle_index), 0);
    const current = {
      runId: run.id,
      cycleIndex,
      linked: Math.max(toCount((summary as { linked_in_cycle?: number }).linked_in_cycle), 0),
      failed: Math.max(toCount((summary as { failed_in_cycle?: number }).failed_in_cycle), 0),
    };
    const previous = previousCountersRef.current;
    previousCountersRef.current = current;

    if (!previous || previous.runId !== current.runId) {
      return;
    }
    if (previous.cycleIndex !== current.cycleIndex) {
      return;
    }

    if (current.linked > previous.linked) {
      showInfo(t("toasts.tecdocApiLinkedCount", { count: current.linked }));
    }
    if (current.failed > previous.failed) {
      showWarning(t("toasts.tecdocApiErrorsCount", { count: current.failed }));
    }
  }, [enableToasts, run, showInfo, showWarning, t]);

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
