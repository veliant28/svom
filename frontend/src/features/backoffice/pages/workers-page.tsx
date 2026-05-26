"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  LoaderCircle,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  TriangleAlert,
  WifiOff,
  XOctagon,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { getBackofficeWorkersDashboard, runBackofficeWorkerAction } from "@/features/backoffice/api/backoffice-api";
import { OperationsRoleSwitcher } from "@/features/backoffice/components/dashboard/operations-role-switcher";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { EchartsPanel } from "@/features/backoffice/components/widgets/echarts-panel";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip, type StatusChipTone } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapability } from "@/features/backoffice/lib/capabilities";
import type {
  BackofficeWorkerTask,
  BackofficeWorkerTaskStatus,
  BackofficeWorker,
  BackofficeWorkersDashboard,
  BackofficeWorkerStatus,
} from "@/features/backoffice/types/worker-monitor.types";
import { useAuth } from "@/features/auth/hooks/use-auth";

type ActiveTaskRow = {
  key: string;
  taskId: string;
  taskName: string;
  workerName: string;
  taskStatus: BackofficeWorkerTaskStatus;
  workerStatus: BackofficeWorkerStatus;
  cpuPercent: number;
  runtimeSeconds: number;
  reservedCount: number;
  startedAtText: string;
};

function formatDuration(secondsRaw: number): string {
  const seconds = Math.max(0, Math.floor(secondsRaw));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function resolveStatusVisual(status: BackofficeWorkerStatus): { tone: StatusChipTone; icon: LucideIcon; iconClassName: string } {
  if (status === "active") {
    return {
      tone: "blue",
      icon: LoaderCircle,
      iconClassName: "worker-badge-active",
    };
  }
  if (status === "idle") {
    return {
      tone: "info",
      icon: Pause,
      iconClassName: "worker-badge-idle",
    };
  }
  if (status === "stuck") {
    return {
      tone: "warning",
      icon: TriangleAlert,
      iconClassName: "worker-badge-stuck",
    };
  }
  return {
    tone: "gray",
    icon: WifiOff,
    iconClassName: "worker-badge-offline",
  };
}

function StatusBadge({
  status,
  label,
}: {
  status: BackofficeWorkerStatus;
  label: string;
}) {
  const visual = resolveStatusVisual(status);
  const Icon = visual.icon;

  return (
    <StatusChip tone={visual.tone} icon={Icon} className={visual.iconClassName}>
      {label}
    </StatusChip>
  );
}

function resolveWorkerCpuColor(worker?: BackofficeWorker): string {
  if (!worker) {
    return "#94a3b8";
  }
  if (!worker.online) {
    return "#71717a";
  }
  if (worker.stuck) {
    return "#f59e0b";
  }
  if (worker.active_count > 0) {
    return "#10b981";
  }
  return "#0ea5e9";
}

function buildTaskRows(
  workers: BackofficeWorker[],
  elapsedSeconds: number,
  includeLiveRuntime: boolean,
): ActiveTaskRow[] {
  const rows: ActiveTaskRow[] = [];

  for (const worker of workers) {
    const tasksFromApi = worker.current_tasks ?? [];
    const taskList: BackofficeWorkerTask[] = tasksFromApi.length > 0
      ? tasksFromApi
      : (worker.current_task_ids ?? []).map((taskId, index) => ({
        task_id: taskId,
        task_name: worker.current_task_names?.[index] || "",
        runtime_seconds: worker.longest_task_seconds,
        status: worker.status === "stuck" ? "stuck" : "active",
        started_at: worker.last_seen_at,
      }));

    if (!taskList.length) {
      continue;
    }

    const perTaskCpu = worker.cpu_percent / Math.max(taskList.length, 1);

    taskList.forEach((task, index) => {
      const taskId = String(task.task_id || "").trim();
      const fallbackName = taskId || `${worker.name}-${index + 1}`;
      const taskName = String(task.task_name || "").trim() || fallbackName;
      const runtimeBase = Number.isFinite(task.runtime_seconds) ? Math.max(0, task.runtime_seconds) : 0;
      const runtimeSeconds = includeLiveRuntime && worker.online && worker.active_count > 0
        ? runtimeBase + elapsedSeconds
        : runtimeBase;

      rows.push({
        key: `${worker.name}:${taskId || index}`,
        taskId,
        taskName,
        taskStatus: task.status || "active",
        workerName: worker.name,
        workerStatus: worker.status,
        cpuPercent: Number(perTaskCpu.toFixed(2)),
        runtimeSeconds,
        reservedCount: worker.reserved_count,
        startedAtText: formatDateTime(task.started_at || worker.last_seen_at),
      });
    });
  }

  rows.sort((left, right) => {
    const leftWeight = (left.taskStatus === "stuck" ? 1000 : 0) + left.runtimeSeconds;
    const rightWeight = (right.taskStatus === "stuck" ? 1000 : 0) + right.runtimeSeconds;
    return rightWeight - leftWeight;
  });

  return rows.slice(0, 200);
}

function WorkerKillConfirmModal({
  worker,
  taskId,
  onClose,
  onConfirm,
  isSubmitting,
  t,
}: {
  worker: string;
  taskId: string;
  onClose: () => void;
  onConfirm: () => void;
  isSubmitting: boolean;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("workers.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div
        className="relative z-10 w-full max-w-md rounded-xl border p-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-sm font-semibold">{t("workers.killModal.title")}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("workers.killModal.message", { worker, taskId })}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "#ef4444", backgroundColor: "#dc2626", color: "#ffffff" }}
            onClick={onConfirm}
          >
            {isSubmitting ? t("loading") : t("workers.actions.kill")}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("workers.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function WorkersPage() {
  const tCommon = useTranslations("backoffice.common");
  const tNav = useTranslations("backoffice.navigation");
  const tDashboard = useTranslations("backoffice.dashboard");
  const { user } = useAuth();
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();
  const canManageWorkers = hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.workersManage);

  const [submittingWorker, setSubmittingWorker] = useState("");
  const [killModal, setKillModal] = useState<{ worker: string; taskId: string } | null>(null);
  const [liveNowMs, setLiveNowMs] = useState(() => Date.now());
  const [refreshNonce, setRefreshNonce] = useState(0);

  const queryFn = useCallback((token: string) => getBackofficeWorkersDashboard(token), []);
  const workersState = useBackofficeQuery<BackofficeWorkersDashboard>(queryFn);
  const rawWorkersRefetch = workersState.refetch;

  const isRefetchingWorkersRef = useRef(false);
  const hasQueuedWorkersRefetchRef = useRef(false);
  const refetchWorkers = useCallback(async () => {
    if (isRefetchingWorkersRef.current) {
      hasQueuedWorkersRefetchRef.current = true;
      return;
    }

    isRefetchingWorkersRef.current = true;
    try {
      do {
        hasQueuedWorkersRefetchRef.current = false;
        await rawWorkersRefetch();
      } while (hasQueuedWorkersRefetchRef.current);
    } finally {
      isRefetchingWorkersRef.current = false;
    }
  }, [rawWorkersRefetch]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refetchWorkers();
    }, 5000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [refetchWorkers]);

  useEffect(() => {
    if (refreshNonce <= 0) {
      return;
    }
    void refetchWorkers();
  }, [refreshNonce, refetchWorkers]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setLiveNowMs(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  const workers = useMemo(() => workersState.data?.workers ?? [], [workersState.data?.workers]);
  const workersByName = useMemo(() => new Map(workers.map((worker) => [worker.name, worker] as const)), [workers]);
  const snapshotMs = useMemo(() => {
    const raw = workersState.data?.generated_at;
    if (!raw) {
      return liveNowMs;
    }
    const parsed = new Date(raw).getTime();
    return Number.isFinite(parsed) ? parsed : liveNowMs;
  }, [liveNowMs, workersState.data?.generated_at]);

  const activeTaskRows = useMemo<ActiveTaskRow[]>(() => {
    const elapsedSeconds = Math.max(0, Math.floor((liveNowMs - snapshotMs) / 1000));
    return buildTaskRows(workers, elapsedSeconds, true);
  }, [liveNowMs, snapshotMs, workers]);
  const activeTaskRowsForCharts = useMemo<ActiveTaskRow[]>(() => {
    return buildTaskRows(workers, 0, false);
  }, [workers]);
  const primaryWorker = workers[0] ?? null;
  const isDarkTheme = typeof document !== "undefined" && document.documentElement.classList.contains("theme-dark");
  const chartTextColor = isDarkTheme ? "#d6e2eb" : "#475569";
  const chartSubtleTextColor = isDarkTheme ? "#c7d8e5" : "#64748b";
  const chartAxisLineColor = isDarkTheme ? "#4b6070" : "#cbd5e1";
  const chartGridColor = isDarkTheme ? "#31434f" : "#e2e8f0";
  const chartMetricColor = isDarkTheme ? "#e8edf1" : "#0f172a";
  const metaTextColor = isDarkTheme ? "#b9cbd9" : "var(--muted)";
  const taskCounts = useMemo(() => {
    const active = activeTaskRows.length;
    const idle = workers.reduce((acc, worker) => acc + Math.max(0, worker.reserved_count) + Math.max(0, worker.scheduled_count), 0);
    const stuck = activeTaskRows.filter((task) => task.taskStatus === "stuck").length;
    const offline = workers.reduce((acc, worker) => {
      if (worker.status !== "offline") {
        return acc;
      }
      return acc + Math.max(0, worker.reserved_count) + Math.max(0, worker.scheduled_count);
    }, 0);
    return { active, idle, stuck, offline };
  }, [activeTaskRows, workers]);

  const cpuOption = useMemo(() => {
    const history = workersState.data?.cpu_history ?? [];
    const prioritized = [...activeTaskRowsForCharts]
      .sort((left, right) => right.cpuPercent - left.cpuPercent)
      .slice(0, 12);

    const axis = history.map((item) => {
      const date = new Date(item.timestamp);
      return Number.isNaN(date.getTime())
        ? "--:--"
        : new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
    });
    const maxHistoryCpu = history.reduce((acc, sample) => {
      const values = Object.values(sample.workers || {});
      if (values.length === 0) {
        return acc;
      }
      const sampleMax = Math.max(...values);
      return Number.isFinite(sampleMax) ? Math.max(acc, sampleMax) : acc;
    }, 0);
    const yAxisMax = Math.max(10, Math.min(100, Math.ceil((maxHistoryCpu * 1.25) / 5) * 5 || 10));

    return {
      animationDuration: 280,
      grid: { left: 24, right: 20, top: 28, bottom: 22, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: isDarkTheme ? "rgba(23,33,38,0.96)" : "#ffffff",
        borderColor: chartAxisLineColor,
        borderWidth: 1,
        textStyle: { color: chartMetricColor, fontSize: 11 },
      },
      legend: {
        top: 0,
        type: "scroll",
        textStyle: { color: chartSubtleTextColor, fontSize: 11 },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: axis,
        axisLabel: { color: chartSubtleTextColor, fontSize: 11 },
        axisLine: { lineStyle: { color: chartAxisLineColor } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: yAxisMax,
        axisLabel: { color: chartSubtleTextColor, fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: chartGridColor } },
      },
      series: prioritized.map((task) => {
        const worker = workersByName.get(task.workerName);
        const lineColor = resolveWorkerCpuColor(worker);
        const taskLabel = task.taskName.split(".").pop() || task.taskName;
        const displayName = `${taskLabel} • ${task.taskId.slice(0, 8)}`;
        return {
          name: displayName,
          type: "line",
          color: lineColor,
          smooth: false,
          connectNulls: false,
          symbol: "none",
          itemStyle: { color: lineColor },
          lineStyle: { width: 2, color: lineColor },
          areaStyle: { color: lineColor, opacity: 0.12 },
          emphasis: { disabled: true },
          data: history.map((item) => {
            const rawValue = item.workers?.[task.workerName];
            if (typeof rawValue !== "number" || !Number.isFinite(rawValue)) {
              return null;
            }
            const divisor = Math.max((workersByName.get(task.workerName)?.current_task_ids?.length ?? 1), 1);
            return Number((rawValue / divisor).toFixed(2));
          }),
        };
      }),
    };
  }, [activeTaskRowsForCharts, chartAxisLineColor, chartGridColor, chartMetricColor, chartSubtleTextColor, isDarkTheme, workersByName, workersState.data?.cpu_history]);

  const currentTasksOption = useMemo(() => {
    const rows = [...activeTaskRowsForCharts].slice(0, 20);
    return {
      animationDuration: 220,
      grid: { left: 88, right: 16, top: 14, bottom: 14, containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: isDarkTheme ? "rgba(23,33,38,0.96)" : "#ffffff",
        borderColor: chartAxisLineColor,
        borderWidth: 1,
        textStyle: { color: chartMetricColor, fontSize: 11 },
      },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: chartSubtleTextColor, fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: chartGridColor } },
      },
      yAxis: {
        type: "category",
        data: rows.map((item) => (item.taskName.split(".").pop() || item.taskName).slice(0, 42)),
        axisLabel: { color: chartTextColor, fontSize: 11 },
      },
      series: [
        {
          type: "bar",
          data: rows.map((item) => item.cpuPercent),
          label: { show: true, position: "right", color: chartMetricColor, fontSize: 11, formatter: "{c}%" },
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: (params: { dataIndex: number }) => {
              const worker = workersByName.get(rows[params.dataIndex]?.workerName || "");
              return resolveWorkerCpuColor(worker);
            },
          },
        },
      ],
    };
  }, [activeTaskRowsForCharts, chartAxisLineColor, chartGridColor, chartMetricColor, chartSubtleTextColor, chartTextColor, isDarkTheme, workersByName]);

  const performAction = useCallback(async (
    action: "stop" | "pause" | "resume" | "restart" | "kill_task",
    worker: BackofficeWorker,
    options?: { taskId?: string },
  ) => {
    if (!workersState.token || !canManageWorkers) {
      return;
    }

    setSubmittingWorker(worker.name);
    try {
      const response = await runBackofficeWorkerAction(workersState.token, {
        action,
        worker: worker.name,
        queues: worker.queues,
        task_id: options?.taskId,
      });
      if (response.status === "ok") {
        showSuccess(tCommon("workers.toasts.actionSuccess", { action: tCommon(`workers.actions.${action}` as never), worker: worker.name }));
      } else {
        showWarning(tCommon("workers.toasts.actionWarning"));
      }
      await refetchWorkers();
    } catch (error) {
      showApiError(error, tCommon("workers.toasts.actionFailed"));
    } finally {
      setSubmittingWorker("");
    }
  }, [canManageWorkers, refetchWorkers, showApiError, showSuccess, showWarning, tCommon, workersState.token]);

  return (
    <>
      <PageHeader
        title={tCommon("workers.title")}
        description={tCommon("workers.subtitle")}
        actions={(
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              setRefreshNonce((prev) => prev + 1);
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {tCommon("workers.actions.refresh")}
          </button>
        )}
        switcher={canManageWorkers ? (
          <OperationsRoleSwitcher
            activeTab="workers"
            dashboardHref="/backoffice"
            managersHref="/backoffice/operations/managers"
            operatorsHref="/backoffice/operations/operators"
            workersHref="/backoffice/workers"
            dashboardLabel={tDashboard("staff.roles.dashboard")}
            managersLabel={tDashboard("staff.roles.managers")}
            operatorsLabel={tDashboard("staff.roles.operators")}
            workersLabel={tNav("workers")}
            ariaLabel={tDashboard("staff.switcherAriaLabel")}
          />
        ) : null}
      />

      <AsyncState
        isLoading={workersState.isLoading && !workersState.data}
        error={workersState.error}
        empty={false}
        emptyLabel=""
      >
        <section className="grid h-[calc(100vh-11rem)] min-h-[560px] grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden">
        <article className="rounded-2xl border p-3 lg:p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <StatusBadge status="active" label={`${tCommon("workers.badges.active")}: ${taskCounts.active}`} />
            <StatusBadge status="idle" label={`${tCommon("workers.badges.idle")}: ${taskCounts.idle}`} />
            <StatusBadge status="stuck" label={`${tCommon("workers.badges.stuck")}: ${taskCounts.stuck}`} />
            <StatusBadge status="offline" label={`${tCommon("workers.badges.offline")}: ${taskCounts.offline}`} />
            <span className="ml-auto text-xs" style={{ color: metaTextColor }}>
              {tCommon("workers.updatedAt", { value: formatDateTime(workersState.data?.generated_at || "") })}
            </span>
          </div>
          <EchartsPanel
            option={cpuOption}
            hasData={(workersState.data?.cpu_history?.length ?? 0) > 1}
            emptyLabel={tCommon("workers.empty")}
            className="h-[250px] w-full"
          />
        </article>

        <article className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-2 rounded-2xl border p-3 lg:p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">{tCommon("workers.currentTasks")}</h2>
            <span className="text-xs" style={{ color: metaTextColor }}>
              {tCommon("workers.total", { count: activeTaskRows.length })}
            </span>
          </div>

          <div className="grid min-h-0 grid-rows-[minmax(0,0.45fr)_minmax(0,0.55fr)] gap-2">
            <div className="grid min-h-0 gap-2 lg:grid-cols-[44px_minmax(0,1fr)]">
              <div className="flex h-full flex-col items-center justify-center gap-1">
                <ActionIconButton
                  label={tCommon("workers.actions.pause")}
                  icon={Pause}
                  disabled={!primaryWorker || submittingWorker === primaryWorker.name || !primaryWorker.online || primaryWorker.queues.length === 0}
                  onClick={() => {
                    if (!primaryWorker) return;
                    void performAction("pause", primaryWorker);
                  }}
                />
                <ActionIconButton
                  label={tCommon("workers.actions.resume")}
                  icon={Play}
                  disabled={!primaryWorker || submittingWorker === primaryWorker.name || !primaryWorker.online || primaryWorker.queues.length === 0}
                  onClick={() => {
                    if (!primaryWorker) return;
                    void performAction("resume", primaryWorker);
                  }}
                />
                <ActionIconButton
                  label={tCommon("workers.actions.restart")}
                  icon={RotateCcw}
                  disabled={!primaryWorker || submittingWorker === primaryWorker.name || !primaryWorker.online}
                  onClick={() => {
                    if (!primaryWorker) return;
                    void performAction("restart", primaryWorker);
                  }}
                />
                <ActionIconButton
                  label={tCommon("workers.actions.stop")}
                  icon={Square}
                  disabled={!primaryWorker || submittingWorker === primaryWorker.name || !primaryWorker.online}
                  onClick={() => {
                    if (!primaryWorker) return;
                    void performAction("stop", primaryWorker);
                  }}
                />
                {primaryWorker && submittingWorker === primaryWorker.name ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
              </div>

              <EchartsPanel
                option={currentTasksOption}
                hasData={activeTaskRows.length > 0}
                emptyLabel={tCommon("workers.empty")}
                className="h-full w-full"
              />
            </div>

            <div className="min-h-0 overflow-auto rounded-xl border" style={{ borderColor: "var(--border)" }}>
              <div className="grid gap-1 p-2">
                {activeTaskRows.map((task) => {
                  const worker = workersByName.get(task.workerName);
                  if (!worker) {
                    return null;
                  }
                  const isSubmitting = submittingWorker === worker.name;
                  const statusLabel = tCommon(`workers.status.${task.taskStatus}` as never);
                  const activeTaskId = task.taskId || "";
                  const title = task.taskName.split(".").pop() || task.taskName;

                  return (
                    <div
                      key={task.key}
                      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg border px-2 py-1.5"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-xs font-semibold">{title}</p>
                          <StatusBadge status={task.taskStatus} label={statusLabel} />
                        </div>
                        <p className="mt-1 truncate text-[11px]" style={{ color: metaTextColor }}>
                          {tCommon("workers.rowTaskMeta", {
                            taskId: task.taskId.slice(0, 8),
                            worker: task.workerName,
                            cpu: task.cpuPercent.toFixed(1),
                            reserved: task.reservedCount,
                            runtime: formatDuration(task.runtimeSeconds),
                          })}
                        </p>
                        <p className="truncate text-[11px]" style={{ color: metaTextColor }}>
                          {tCommon("workers.taskStartedAt", { value: task.startedAtText })}
                        </p>
                      </div>

                      <div className="flex items-center gap-1">
                        <ActionIconButton
                          label={tCommon("workers.actions.kill")}
                          icon={XOctagon}
                          tone="danger"
                          dangerFill
                          disabled={isSubmitting || !activeTaskId}
                          onClick={() => {
                            if (!activeTaskId) {
                              return;
                            }
                            setKillModal({ worker: worker.name, taskId: activeTaskId });
                          }}
                        />
                        {isSubmitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </article>
        </section>
      </AsyncState>

      {killModal ? (
        <WorkerKillConfirmModal
          worker={killModal.worker}
          taskId={killModal.taskId}
          onClose={() => setKillModal(null)}
          onConfirm={() => {
            const worker = workers.find((item) => item.name === killModal.worker);
            if (!worker) {
              setKillModal(null);
              return;
            }
            void performAction("kill_task", worker, { taskId: killModal.taskId }).finally(() => {
              setKillModal(null);
            });
          }}
          isSubmitting={Boolean(submittingWorker)}
          t={tCommon}
        />
      ) : null}
    </>
  );
}
