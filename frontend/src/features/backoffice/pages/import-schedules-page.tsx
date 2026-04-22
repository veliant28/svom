"use client";

import { useCallback, useState } from "react";
import { Check, Power, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

import { getBackofficeImportSchedules, updateBackofficeImportSchedule } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeImportSource } from "@/features/backoffice/types/backoffice";
import { useTheme } from "@/shared/components/theme/theme-provider";

type ScheduleDraft = {
  schedule_run_time: string;
  schedule_timezone: string;
  schedule_every_day: boolean;
};

function buildDraft(item: BackofficeImportSource): ScheduleDraft {
  return {
    schedule_run_time: item.schedule_run_time || "01:00",
    schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
    schedule_every_day: item.schedule_every_day !== false,
  };
}

export function ImportSchedulesPage() {
  const t = useTranslations("backoffice.common");
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const monoActiveBackground = isDark ? "#ffffff" : "#000000";
  const monoActiveText = isDark ? "#111111" : "#ffffff";
  const [q, setQ] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ScheduleDraft>>({});
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeImportSchedules(token, {
        q,
      }),
    [q],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportSource[] }>(queryFn, [q]);
  const rows = data?.results ?? [];
  const getDraft = useCallback(
    (item: BackofficeImportSource): ScheduleDraft => drafts[item.id] ?? buildDraft(item),
    [drafts],
  );

  async function saveScheduleTime(item: BackofficeImportSource, runTime: string) {
    if (!token) return;
    const sourceLabel = item.code.toUpperCase();
    const normalizedRunTime = runTime || "01:00";
    if (normalizedRunTime === (item.schedule_run_time || "01:00")) {
      return;
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
      showSuccess(t("importSchedules.messages.scheduleSaved", { source: sourceLabel }));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
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
              render: (item) => item.next_run || "-",
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
                        errors: item.last_run.errors_count,
                      })}
                    </p>
                  </div>
                ) : (
                  "-"
                ),
            },
            {
              key: "scenario",
              label: t("importSchedules.table.columns.pipeline"),
              render: () => (
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {scenarioLabel}
                </p>
              ),
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
                  <ActionIconButton
                    label={t("importSchedules.actions.saveSchedule")}
                    icon={Check}
                    onClick={() => {
                      void saveScheduleTime(item, getDraft(item).schedule_run_time);
                    }}
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
