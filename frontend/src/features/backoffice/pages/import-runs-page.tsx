"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeImportRuns,
  runRepriceAfterImportAction,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeImportRun } from "@/features/backoffice/types/backoffice";

export function ImportRunsPage() {
  const t = useTranslations("backoffice.importRuns");
  const tStatus = useTranslations("backoffice.common");
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeImportRuns(token, {
        q,
        status: statusFilter,
        source: sourceFilter,
      }),
    [q, statusFilter, sourceFilter],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportRun[] }>(queryFn, [q, statusFilter, sourceFilter]);
  const runs = data?.results ?? [];

  const sourceOptions = Array.from(new Set(runs.map((run) => run.source_code))).sort();

  async function reprice(runId: string) {
    if (!token) {
      return;
    }

    try {
      const response = await runRepriceAfterImportAction(token, {
        run_id: runId,
        dispatch_async: false,
      });

      showSuccess(t("actions.repriceDone", { mode: response.mode }));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("actions.repriceFailed"));
    }
  }

  return (
    <section>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <button
            type="button"
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void refetch();
            }}
          >
            {t("actions.refresh")}
          </button>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("filters.search")}
          className="h-9 min-w-[220px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allStatuses")}</option>
          <option value="pending">{tStatus("statuses.pending")}</option>
          <option value="running">{tStatus("statuses.running")}</option>
          <option value="success">{tStatus("statuses.success")}</option>
          <option value="partial">{tStatus("statuses.partial")}</option>
          <option value="failed">{tStatus("statuses.failed")}</option>
        </select>
        <select
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allSources")}</option>
          {sourceOptions.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!runs.length} emptyLabel={t("states.empty")}>
        <BackofficeTable
          emptyLabel={t("states.empty")}
          rows={runs}
          columns={[
            {
              key: "source",
              label: t("table.columns.source"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{item.source_name}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {item.source_code}
                  </p>
                </div>
              ),
            },
            {
              key: "status",
              label: t("table.columns.status"),
              render: (item) => <StatusChip status={item.status} />,
            },
            {
              key: "rows",
              label: t("table.columns.rows"),
              render: (item) => item.processed_rows,
            },
            {
              key: "offers",
              label: t("table.columns.offers"),
              render: (item) => `${item.offers_created}/${item.offers_updated}`,
            },
            {
              key: "errors",
              label: t("table.columns.errors"),
              render: (item) => item.errors_count,
            },
            {
              key: "repriced",
              label: t("table.columns.repriced"),
              render: (item) => item.repriced_products,
            },
            {
              key: "actions",
              label: t("table.columns.actions"),
              render: (item) => (
                <button
                  type="button"
                  className="h-8 rounded-md border px-2 text-xs"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  onClick={() => {
                    void reprice(item.id);
                  }}
                >
                  {t("actions.reprice")}
                </button>
              ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
