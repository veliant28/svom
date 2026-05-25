"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
  BackofficeWorker,
  BackofficeWorkersDashboard,
  BackofficeWorkerStatus,
} from "@/features/backoffice/types/worker-monitor.types";
import { useAuth } from "@/features/auth/hooks/use-auth";

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

  const queryFn = useCallback((token: string) => getBackofficeWorkersDashboard(token), []);
  const workersState = useBackofficeQuery<BackofficeWorkersDashboard>(queryFn);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void workersState.refetch();
    }, 5000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [workersState]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setLiveNowMs(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  const workers = useMemo(() => workersState.data?.workers ?? [], [workersState.data?.workers]);
  const counts = workersState.data?.status_counts ?? { active: 0, idle: 0, stuck: 0, offline: 0 };
  const snapshotMs = useMemo(() => {
    const raw = workersState.data?.generated_at;
    if (!raw) {
      return liveNowMs;
    }
    const parsed = new Date(raw).getTime();
    return Number.isFinite(parsed) ? parsed : liveNowMs;
  }, [liveNowMs, workersState.data?.generated_at]);

  const cpuOption = useMemo(() => {
    const history = workersState.data?.cpu_history ?? [];
    const workerByName = new Map(workers.map((worker) => [worker.name, worker] as const));
    const workerNames = new Set<string>();
    for (const sample of history) {
      Object.keys(sample.workers || {}).forEach((name) => workerNames.add(name));
    }

    const prioritized = [...workerNames]
      .sort((left, right) => {
        const leftWorker = workers.find((item) => item.name === left);
        const rightWorker = workers.find((item) => item.name === right);
        const leftWeight = (leftWorker?.stuck ? 1000 : 0) + (leftWorker?.active_count || 0) * 20 + (leftWorker?.cpu_percent || 0);
        const rightWeight = (rightWorker?.stuck ? 1000 : 0) + (rightWorker?.active_count || 0) * 20 + (rightWorker?.cpu_percent || 0);
        return rightWeight - leftWeight;
      })
      .slice(0, 10);

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
      tooltip: { trigger: "axis" },
      legend: {
        top: 0,
        type: "scroll",
        textStyle: { color: "#64748b", fontSize: 11 },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: axis,
        axisLabel: { color: "#64748b", fontSize: 11 },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: yAxisMax,
        axisLabel: { color: "#64748b", fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      series: prioritized.map((workerName) => {
        const worker = workerByName.get(workerName);
        const lineColor = resolveWorkerCpuColor(worker);
        return {
          name: workerName,
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
            const rawValue = item.workers?.[workerName];
            if (typeof rawValue !== "number" || !Number.isFinite(rawValue)) {
              return null;
            }
            return Number(rawValue.toFixed(2));
          }),
        };
      }),
    };
  }, [workers, workersState.data?.cpu_history]);

  const currentWorkersOption = useMemo(() => {
    const rows = [...workers].slice(0, 12);
    return {
      animationDuration: 220,
      grid: { left: 88, right: 16, top: 14, bottom: 14, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: "#64748b", fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      yAxis: {
        type: "category",
        data: rows.map((item) => item.name.replace("celery@", "")),
        axisLabel: { color: "#64748b", fontSize: 11 },
      },
      series: [
        {
          type: "bar",
          data: rows.map((item) => item.cpu_percent),
          label: { show: true, position: "right", color: "#0f172a", fontSize: 11, formatter: "{c}%" },
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: (params: { dataIndex: number }) => {
              const worker = rows[params.dataIndex];
              return resolveWorkerCpuColor(worker);
            },
          },
        },
      ],
    };
  }, [workers]);

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
      await workersState.refetch();
    } catch (error) {
      showApiError(error, tCommon("workers.toasts.actionFailed"));
    } finally {
      setSubmittingWorker("");
    }
  }, [canManageWorkers, showApiError, showSuccess, showWarning, tCommon, workersState]);

  const handleManualRefresh = useCallback(async () => {
    await workersState.refetch();
  }, [workersState]);

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
              void handleManualRefresh();
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
            <StatusBadge status="active" label={`${tCommon("workers.badges.active")}: ${counts.active}`} />
            <StatusBadge status="idle" label={`${tCommon("workers.badges.idle")}: ${counts.idle}`} />
            <StatusBadge status="stuck" label={`${tCommon("workers.badges.stuck")}: ${counts.stuck}`} />
            <StatusBadge status="offline" label={`${tCommon("workers.badges.offline")}: ${counts.offline}`} />
            <span className="ml-auto text-xs" style={{ color: "var(--muted)" }}>
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
            <h2 className="text-sm font-semibold">{tCommon("workers.currentWorkers")}</h2>
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              {tCommon("workers.total", { count: workers.length })}
            </span>
          </div>

          <div className="grid min-h-0 grid-rows-[minmax(0,0.48fr)_minmax(0,0.52fr)] gap-2">
            <EchartsPanel
              option={currentWorkersOption}
              hasData={workers.length > 0}
              emptyLabel={tCommon("workers.empty")}
              className="h-full w-full"
            />

            <div className="min-h-0 overflow-auto rounded-xl border" style={{ borderColor: "var(--border)" }}>
              <div className="grid gap-1 p-2">
                {workers.map((worker) => {
                  const isSubmitting = submittingWorker === worker.name;
                  const statusLabel = tCommon(`workers.status.${worker.status}` as never);
                  const hasActiveTask = worker.current_task_ids.length > 0;
                  const activeTaskId = worker.current_task_ids[0] || "";
                  const liveRuntimeSeconds = (() => {
                    if (!worker.online || worker.active_count <= 0) {
                      return worker.longest_task_seconds;
                    }
                    const elapsed = Math.max(0, Math.floor((liveNowMs - snapshotMs) / 1000));
                    return worker.longest_task_seconds + elapsed;
                  })();

                  return (
                    <div
                      key={worker.name}
                      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg border px-2 py-1.5"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-xs font-semibold">{worker.name}</p>
                          <StatusBadge status={worker.status} label={statusLabel} />
                        </div>
                        <p className="mt-1 truncate text-[11px]" style={{ color: "var(--muted)" }}>
                          {tCommon("workers.rowMeta", {
                            cpu: worker.cpu_percent.toFixed(1),
                            active: worker.active_count,
                            reserved: worker.reserved_count,
                            runtime: formatDuration(liveRuntimeSeconds),
                          })}
                        </p>
                      </div>

                      <div className="flex items-center gap-1">
                        <ActionIconButton
                          label={tCommon("workers.actions.pause")}
                          icon={Pause}
                          disabled={isSubmitting || !worker.online || worker.queues.length === 0}
                          onClick={() => {
                            void performAction("pause", worker);
                          }}
                        />
                        <ActionIconButton
                          label={tCommon("workers.actions.resume")}
                          icon={Play}
                          disabled={isSubmitting || !worker.online || worker.queues.length === 0}
                          onClick={() => {
                            void performAction("resume", worker);
                          }}
                        />
                        <ActionIconButton
                          label={tCommon("workers.actions.restart")}
                          icon={RotateCcw}
                          disabled={isSubmitting || !worker.online}
                          onClick={() => {
                            void performAction("restart", worker);
                          }}
                        />
                        <ActionIconButton
                          label={tCommon("workers.actions.stop")}
                          icon={Square}
                          disabled={isSubmitting || !worker.online}
                          onClick={() => {
                            void performAction("stop", worker);
                          }}
                        />
                        <ActionIconButton
                          label={tCommon("workers.actions.kill")}
                          icon={XOctagon}
                          tone="danger"
                          disabled={isSubmitting || !hasActiveTask}
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
