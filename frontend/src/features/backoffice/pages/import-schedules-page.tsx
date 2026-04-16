"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeImportSchedules, updateBackofficeImportSchedule } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeImportSource } from "@/features/backoffice/types/backoffice";

export function ImportSchedulesPage() {
  const t = useTranslations("backoffice.common");
  const [q, setQ] = useState("");
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

  async function toggleAutoImport(item: BackofficeImportSource) {
    if (!token) return;
    try {
      await updateBackofficeImportSchedule(token, item.id, {
        is_auto_import_enabled: !item.is_auto_import_enabled,
      });
      showSuccess(t("importSchedules.messages.scheduleUpdated", { source: item.code }));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
    }
  }

  async function saveDefaultCron(item: BackofficeImportSource) {
    if (!token) return;
    try {
      await updateBackofficeImportSchedule(token, item.id, {
        schedule_cron: item.schedule_cron || "*/30 * * * *",
        schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
        auto_reprice_after_import: item.auto_reprice_after_import,
        auto_reindex_after_import: item.auto_reindex_after_import,
      });
      showSuccess(t("importSchedules.messages.scheduleSaved", { source: item.code }));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
    }
  }

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
              key: "enabled",
              label: t("importSchedules.table.columns.enabled"),
              render: (item) => <StatusChip status={item.is_auto_import_enabled ? "enabled" : "disabled"} />,
            },
            {
              key: "cron",
              label: t("importSchedules.table.columns.cron"),
              render: (item) => (
                <div>
                  <p>{item.schedule_cron || "-"}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {item.schedule_timezone}
                  </p>
                </div>
              ),
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
              key: "actions",
              label: t("importSchedules.table.columns.actions"),
              render: (item) => (
                <div className="flex flex-wrap gap-1">
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void toggleAutoImport(item);
                    }}
                  >
                    {item.is_auto_import_enabled ? t("importSchedules.actions.disable") : t("importSchedules.actions.enable")}
                  </button>
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void saveDefaultCron(item);
                    }}
                  >
                    {t("importSchedules.actions.saveDefaults")}
                  </button>
                </div>
              ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
