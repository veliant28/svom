"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Check, Power, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

import { getBackofficeImportRun, getBackofficeImportSchedules, runBackofficeImportSchedule, updateBackofficeImportSchedule } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeImportRun, BackofficeImportSource } from "@/features/backoffice/types/backoffice";
import { useTheme } from "@/shared/components/theme/theme-provider";

type ScheduleDraft = {
  schedule_run_time: string;
  schedule_timezone: string;
  schedule_every_day: boolean;
};

type ScenarioStep = {
  label: string;
  order: number;
};

function splitScenarioSteps(raw: string): ScenarioStep[] {
  return raw
    .split(/\s*->\s*/g)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((label, index) => ({ label, order: index }));
}

function normalizeScenarioStepLabel(raw: string): string {
  return raw
    .replace(/[_\s]+/g, " ")
    .trim();
}

function splitScenarioStepParts(label: string): string[] {
  const normalized = normalizeScenarioStepLabel(label);
  const parts = normalized.split("/").map((part) => part.trim()).filter(Boolean);
  if (!parts.length) {
    return [];
  }
  return parts.map((part, index) => (index < parts.length - 1 ? `${part}/` : part));
}

function buildDraft(item: BackofficeImportSource): ScheduleDraft {
  return {
    schedule_run_time: item.schedule_run_time || "01:00",
    schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
    schedule_every_day: item.schedule_every_day !== false,
  };
}

const ACTIVE_IMPORT_RUN_STATUSES = new Set(["pending", "running"]);

type ImportRunStatusSnapshot = {
  status: string;
  finished_at: string | null;
} | null;

function isActiveImportRunSnapshot(run: ImportRunStatusSnapshot): boolean {
  if (!run?.status || run.finished_at) {
    return false;
  }
  return ACTIVE_IMPORT_RUN_STATUSES.has(run.status.toLowerCase());
}

function hasActiveImportRun(item: BackofficeImportSource): boolean {
  return isActiveImportRunSnapshot(item.last_run);
}

function ScheduleRunActionButton({
  item,
  token,
  localRunning,
  runLabel,
  runningLabel,
  onRun,
  onRunFinished,
}: {
  item: BackofficeImportSource;
  token: string | null;
  localRunning: boolean;
  runLabel: string;
  runningLabel: string;
  onRun: () => void;
  onRunFinished: () => void;
}) {
  const [polledRun, setPolledRun] = useState<BackofficeImportRun | null>(null);
  const runId = item.last_run?.id || "";
  const currentRun = polledRun && polledRun.id === runId ? polledRun : item.last_run;
  const isBackendRunning = isActiveImportRunSnapshot(currentRun);
  const runLocked = localRunning || isBackendRunning;

  useEffect(() => {
    setPolledRun(null);
  }, [item.last_run?.finished_at, item.last_run?.id, item.last_run?.status]);

  useEffect(() => {
    if (!token || !runId || !isBackendRunning) {
      return undefined;
    }

    let cancelled = false;
    const pollRun = async () => {
      try {
        const nextRun = await getBackofficeImportRun(token, runId);
        if (cancelled) {
          return;
        }
        setPolledRun(nextRun);
        if (!isActiveImportRunSnapshot(nextRun)) {
          onRunFinished();
        }
      } catch {
        // Keep the button locked on transient polling failures; the next tick will retry.
      }
    };

    void pollRun();
    const intervalId = window.setInterval(() => {
      void pollRun();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isBackendRunning, onRunFinished, runId, token]);

  return (
    <ActionIconButton
      label={runLocked ? runningLabel : runLabel}
      icon={Check}
      disabled={runLocked}
      onClick={onRun}
    />
  );
}

export function ImportSchedulesPage() {
  const t = useTranslations("backoffice.common");
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const monoActiveBackground = isDark ? "#ffffff" : "#000000";
  const monoActiveText = isDark ? "#111111" : "#ffffff";
  const [q, setQ] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ScheduleDraft>>({});
  const [runningBySource, setRunningBySource] = useState<Record<string, boolean>>({});
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeImportSchedules(token, {
        q,
      }),
    [q],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportSource[] }>(queryFn, [q]);
  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const getDraft = useCallback(
    (item: BackofficeImportSource): ScheduleDraft => drafts[item.id] ?? buildDraft(item),
    [drafts],
  );
  const isRunLocked = useCallback(
    (item: BackofficeImportSource) => Boolean(runningBySource[item.id]) || hasActiveImportRun(item),
    [runningBySource],
  );
  const refreshAfterRunFinished = useCallback(() => {
    void refetch();
  }, [refetch]);

  async function saveScheduleTime(item: BackofficeImportSource, runTime: string, options?: { silent?: boolean }) {
    if (!token) return;
    const silent = options?.silent === true;
    const sourceLabel = item.code.toUpperCase();
    const normalizedRunTime = runTime || "01:00";
    if (normalizedRunTime === (item.schedule_run_time || "01:00")) {
      return true;
    }

    try {
      await updateBackofficeImportSchedule(token, item.id, {
        schedule_start_date: null,
        schedule_run_time: normalizedRunTime,
        schedule_every_day: true,
        schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
        auto_reprice_after_import: item.auto_reprice_after_import,
        auto_reindex_after_import: item.auto_reindex_after_import,
      });
      if (!silent) {
        showSuccess(t("importSchedules.messages.scheduleSaved", { source: sourceLabel }));
      }
      await refetch();
      return true;
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
      return false;
    }
  }

  async function runScenario(item: BackofficeImportSource) {
    if (!token) return;
    if (isRunLocked(item)) return;
    const sourceLabel = item.code.toUpperCase();
    const draft = getDraft(item);
    const scheduleSaved = await saveScheduleTime(item, draft.schedule_run_time, { silent: true });
    if (!scheduleSaved) {
      return;
    }

    try {
      setRunningBySource((prev) => ({ ...prev, [item.id]: true }));
      const response = await runBackofficeImportSchedule(token, item.id, { dispatch_async: false });
      if (response.mode === "async") {
        showSuccess(t("importSchedules.messages.runQueued", { source: sourceLabel }));
      } else {
        const result = (response.result ?? {}) as { status?: string; detail?: string };
        const status = String(result.status || "").toLowerCase();
        if (status && !["success", "partial"].includes(status)) {
          showApiError(result.detail || t("importSchedules.messages.runFailed"), t("importSchedules.messages.runFailed"));
          return;
        }
        showSuccess(t("importSchedules.messages.runCompleted", { source: sourceLabel }));
      }
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.runFailed"));
    } finally {
      setRunningBySource((prev) => ({ ...prev, [item.id]: false }));
    }
  }

  async function toggleAutoImport(item: BackofficeImportSource) {
    if (!token) return;
    const sourceLabel = item.code.toUpperCase();
    const draft = getDraft(item);
    try {
      await updateBackofficeImportSchedule(token, item.id, {
        is_auto_import_enabled: !item.is_auto_import_enabled,
        schedule_start_date: null,
        schedule_run_time: draft.schedule_run_time || item.schedule_run_time || "01:00",
        schedule_every_day: true,
        schedule_timezone: draft.schedule_timezone || item.schedule_timezone || "Europe/Kyiv",
        auto_reprice_after_import: item.auto_reprice_after_import,
        auto_reindex_after_import: item.auto_reindex_after_import,
      });
      showSuccess(t("importSchedules.messages.scheduleUpdated", { source: sourceLabel }));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
    }
  }

  const scenarioLabel = t("importSchedules.table.pipelineScenario");
  const scenarioSteps = useMemo(() => splitScenarioSteps(scenarioLabel), [scenarioLabel]);
  const scenarioView = useMemo(() => {
    if (!scenarioSteps.length) {
      return (
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          {scenarioLabel}
        </p>
      );
    }

    return (
      <div
        className="inline-flex max-w-full flex-wrap items-center gap-px rounded-[6px] border p-px"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      >
        {scenarioSteps.map((step, stepIndex) => (
          <Fragment key={`scenario-step-${step.order}`}>
            {splitScenarioStepParts(step.label).map((part) => (
              <span
                key={`scenario-step-${step.order}-${part}`}
                className="inline-flex h-6 items-center justify-center rounded-[3px] border px-1.5 text-[11px] font-semibold leading-none whitespace-nowrap"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
              >
                {part}
              </span>
            ))}
            {stepIndex < scenarioSteps.length - 1 ? (
              <span
                className="inline-flex h-6 min-w-6 items-center justify-center rounded-[3px] border px-1 text-[11px] font-semibold leading-none"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--muted)" }}
              >
                →
              </span>
            ) : null}
          </Fragment>
        ))}
      </div>
    );
  }, [scenarioLabel, scenarioSteps]);

  return (
    <section>
      <PageHeader title={t("importSchedules.title")} description={t("importSchedules.subtitle")} />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("importSchedules.filters.search")}
          className="h-9 min-w-[260px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("importSchedules.states.empty")}>
        <BackofficeTable
          emptyLabel={t("importSchedules.states.empty")}
          rows={rows}
          columns={[
            {
              key: "source",
              label: t("importSchedules.table.columns.source"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{item.name}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {item.code} / {item.supplier_code}
                  </p>
                </div>
              ),
            },
            {
              key: "schedule",
              label: t("importSchedules.table.columns.cron"),
              render: (item) => {
                const draft = getDraft(item);
                return (
                  <div className="grid gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
                        {t("importSchedules.schedule.daily")}
                      </span>
                      <span className="text-xs" style={{ color: "var(--muted)" }}>
                        {draft.schedule_timezone || "Europe/Kyiv"}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs" style={{ color: "var(--muted)" }}>
                        {t("importSchedules.schedule.time")}
                      </span>
                      <input
                        type="time"
                        value={draft.schedule_run_time}
                        className="h-8 rounded-md border px-2 text-xs"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        onChange={(event) => {
                          const value = event.target.value;
                          setDrafts((prev) => ({
                            ...prev,
                            [item.id]: {
                              ...(prev[item.id] ?? buildDraft(item)),
                              schedule_run_time: value,
                            },
                          }));
                        }}
                        onBlur={() => {
                          void saveScheduleTime(item, draft.schedule_run_time);
                        }}
                      />
                    </div>
                  </div>
                );
              },
            },
            {
              key: "enabled",
              label: t("importSchedules.table.columns.enabled"),
              render: (item) => <StatusChip status={item.is_auto_import_enabled ? "enabled" : "disabled"} />,
            },
            {
              key: "nextRun",
              label: t("importSchedules.table.columns.nextRun"),
              render: (item) => formatBackofficeDate(item.next_run),
            },
            {
              key: "lastResult",
              label: t("importSchedules.table.columns.lastResult"),
              render: (item) =>
                item.last_run ? (
                  <div>
                    <StatusChip status={item.last_run.status} />
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.table.lastRunSummary", {
                        rows: item.last_run.processed_rows,
                        skipped: item.last_run.offers_skipped,
                      })}
                    </p>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.table.lastRunStarted", { value: formatBackofficeDate(item.last_run.created_at) })}
                    </p>
                    {item.last_run.finished_at ? (
                      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                        {t("importSchedules.table.lastRunFinished", { value: formatBackofficeDate(item.last_run.finished_at) })}
                      </p>
                    ) : null}
                  </div>
                ) : (
                  "-"
                ),
            },
            {
              key: "scenario",
              label: t("importSchedules.table.columns.pipeline"),
              render: () => scenarioView,
            },
            {
              key: "actions",
              label: t("importSchedules.table.columns.actions"),
              render: (item) => (
                  <div className="flex items-center gap-1 whitespace-nowrap">
                    <button
                      type="button"
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors"
                      aria-label={item.is_auto_import_enabled ? t("importSchedules.actions.disable") : t("importSchedules.actions.enable")}
                      style={{
                        borderColor: item.is_auto_import_enabled ? monoActiveBackground : "var(--border)",
                        backgroundColor: item.is_auto_import_enabled ? monoActiveBackground : "var(--surface)",
                        color: item.is_auto_import_enabled ? monoActiveText : "var(--text)",
                      }}
                      onClick={() => {
                        void toggleAutoImport(item);
                      }}
                    >
                      <Power className="h-4 w-4" />
                    </button>
                    <ScheduleRunActionButton
                      item={item}
                      token={token}
                      localRunning={Boolean(runningBySource[item.id])}
                      runLabel={t("importSchedules.actions.runNow")}
                      runningLabel={t("importSchedules.actions.runningNow")}
                      onRun={() => {
                        void runScenario(item);
                      }}
                      onRunFinished={refreshAfterRunFinished}
                    />
                    <ActionIconButton
                      label={t("importSchedules.actions.saveDefaults")}
                      icon={RotateCcw}
                      onClick={() => {
                        const nextDraft: ScheduleDraft = {
                          schedule_run_time: "01:00",
                          schedule_timezone: "Europe/Kyiv",
                          schedule_every_day: true,
                        };
                        setDrafts((prev) => ({
                          ...prev,
                          [item.id]: nextDraft,
                        }));
                        void saveScheduleTime(item, nextDraft.schedule_run_time);
                      }}
                    />
                  </div>
              ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
