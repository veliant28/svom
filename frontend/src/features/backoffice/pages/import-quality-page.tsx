"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeImportQualityCompare,
  getBackofficeImportQualityRuns,
  getBackofficeImportQualitySummary,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatCard } from "@/features/backoffice/components/widgets/stat-card";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type {
  BackofficeImportQuality,
  BackofficeImportQualityComparison,
  BackofficeImportQualitySummary,
} from "@/features/backoffice/types/backoffice";

export function ImportQualityPage() {
  const t = useTranslations("backoffice.importQuality");
  const tCommon = useTranslations("backoffice.common");
  const [source, setSource] = useState("");
  const [requiresAttention, setRequiresAttention] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");

  const summaryQuery = useCallback((token: string) => getBackofficeImportQualitySummary(token), []);
  const runsQuery = useCallback(
    (token: string) =>
      getBackofficeImportQualityRuns(token, {
        source,
        requires_attention: requiresAttention,
      }),
    [source, requiresAttention],
  );
  const compareQuery = useCallback(
    (token: string) => (selectedRunId ? getBackofficeImportQualityCompare(token, selectedRunId) : Promise.resolve(null)),
    [selectedRunId],
  );

  const summary = useBackofficeQuery<BackofficeImportQualitySummary>(summaryQuery);
  const runs = useBackofficeQuery<{ count: number; results: BackofficeImportQuality[] }>(runsQuery, [source, requiresAttention]);
  const compare = useBackofficeQuery<BackofficeImportQualityComparison | null>(compareQuery, [selectedRunId]);

  const rows = runs.data?.results ?? [];
  const sourceOptions = useMemo(() => Array.from(new Set(rows.map((item) => item.source_code))).sort(), [rows]);

  return (
    <section>
      <PageHeader title={t("title")} description={t("subtitle")} />

      <AsyncState
        isLoading={summary.isLoading}
        error={summary.error}
        empty={!summary.data}
        emptyLabel={t("states.emptySummary")}
      >
        {summary.data ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <StatCard title={t("cards.totalRuns")} value={summary.data.totals.total_quality_runs} />
            <StatCard title={t("cards.attentionRuns")} value={summary.data.totals.attention_runs} />
            <StatCard title={t("cards.failedRuns")} value={summary.data.totals.failed_runs} />
            <StatCard title={t("cards.partialRuns")} value={summary.data.totals.partial_runs} />
            <StatCard title={t("cards.avgMatchRate")} value={`${summary.data.totals.avg_match_rate}%`} />
            <StatCard title={t("cards.avgErrorRate")} value={`${summary.data.totals.avg_error_rate}%`} />
          </div>
        ) : null}
      </AsyncState>

      <div className="mt-4 mb-3 flex flex-wrap items-center gap-2">
        <select
          value={source}
          onChange={(event) => setSource(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allSources")}</option>
          {sourceOptions.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={requiresAttention}
          onChange={(event) => setRequiresAttention(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allAttention")}</option>
          <option value="true">{t("filters.attentionOnly")}</option>
          <option value="false">{t("filters.noAttention")}</option>
        </select>
      </div>

      <AsyncState isLoading={runs.isLoading} error={runs.error} empty={!rows.length} emptyLabel={t("states.emptyRuns")}>
        <BackofficeTable
          emptyLabel={t("states.emptyRuns")}
          rows={rows}
          columns={[
            {
              key: "source",
              label: t("table.columns.source"),
              render: (item) => item.source_code,
            },
            {
              key: "status",
              label: t("table.columns.status"),
              render: (item) => <StatusChip status={item.status} />,
            },
            {
              key: "matchRate",
              label: t("table.columns.matchRate"),
              render: (item) => `${item.match_rate}%`,
            },
            {
              key: "errorRate",
              label: t("table.columns.errorRate"),
              render: (item) => `${item.error_rate}%`,
            },
            {
              key: "attention",
              label: t("table.columns.attention"),
              render: (item) => <StatusChip status={item.requires_operator_attention ? "attention" : "ok"} />,
            },
            {
              key: "actions",
              label: t("table.columns.actions"),
              render: (item) => (
                <button
                  type="button"
                  className="h-8 rounded-md border px-2 text-xs"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  onClick={() => setSelectedRunId(item.run_id)}
                >
                  {t("actions.compare")}
                </button>
              ),
            },
          ]}
        />
      </AsyncState>

      {selectedRunId ? (
        <section className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <h2 className="text-sm font-semibold">{t("comparison.title")}</h2>
          <AsyncState
            isLoading={compare.isLoading}
            error={compare.error}
            empty={!compare.data}
            emptyLabel={t("comparison.empty")}
          >
            {compare.data ? (
              <div className="mt-3 grid gap-2 text-sm">
                <p>{t("comparison.matchRateDelta")}: {compare.data.delta.match_rate}%</p>
                <p>{t("comparison.errorRateDelta")}: {compare.data.delta.error_rate}%</p>
                <p>{t("comparison.requiresAttention")}: {compare.data.requires_operator_attention ? tCommon("yes") : tCommon("no")}</p>
              </div>
            ) : null}
          </AsyncState>
        </section>
      ) : null}
    </section>
  );
}
