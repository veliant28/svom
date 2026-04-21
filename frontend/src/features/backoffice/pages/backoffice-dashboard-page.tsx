"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeSummary } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { SimpleBarChart } from "@/features/backoffice/components/widgets/simple-bar-chart";
import { StatCard } from "@/features/backoffice/components/widgets/stat-card";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeSummary } from "@/features/backoffice/types/backoffice";

export function BackofficeDashboardPage() {
  const t = useTranslations("backoffice.dashboard");

  const queryFn = useCallback((token: string) => getBackofficeSummary(token), []);
  const { data, isLoading, error, refetch } = useBackofficeQuery<BackofficeSummary>(queryFn);

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

      <AsyncState isLoading={isLoading} error={error} empty={!data} emptyLabel={t("states.empty")}>
        {data ? (
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard title={t("cards.sources")} value={data.totals.sources} />
              <StatCard title={t("cards.runs")} value={data.totals.import_runs} />
              <StatCard title={t("cards.errors")} value={data.totals.errors_total} subtitle={t("cards.errors24h", { count: data.totals.errors_24h })} />
              <StatCard title={t("cards.repriced")} value={data.totals.repriced_products_total} />
              <StatCard title={t("cards.rawOffers")} value={data.totals.raw_offers} subtitle={t("cards.invalidRawOffers", { count: data.totals.raw_offers_invalid })} />
              <StatCard title={t("cards.supplierOffers")} value={data.totals.supplier_offers} />
              <StatCard title={t("cards.productPrices")} value={data.totals.product_prices} />
            </div>

            {data.quality_summary ? (
              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("quality.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("quality.subtitle", { source: data.quality_summary.source_code })}
                </p>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
                  <p>{t("quality.processed")}: {data.quality_summary.processed_rows}</p>
                  <p>{t("quality.errors")}: {data.quality_summary.errors_count}</p>
                  <p>{t("quality.errorRate")}: {data.quality_summary.error_rate}%</p>
                  <p>{t("quality.skipped")}: {data.quality_summary.offers_skipped}</p>
                </div>
              </section>
            ) : null}

            <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
              <SimpleBarChart
                title={t("charts.runStatuses")}
                items={data.status_buckets.map((item) => ({ label: item.status, value: item.total }))}
              />

              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("latestRuns.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("latestRuns.subtitle")}
                </p>
                <div className="mt-3">
                  <BackofficeTable
                    emptyLabel={t("states.empty")}
                    rows={data.latest_runs}
                    columns={[
                      {
                        key: "source",
                        label: t("latestRuns.columns.source"),
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
                        label: t("latestRuns.columns.status"),
                        render: (item) => <StatusChip status={item.status} />,
                      },
                      {
                        key: "rows",
                        label: t("latestRuns.columns.rows"),
                        render: (item) => item.processed_rows,
                      },
                      {
                        key: "errors",
                        label: t("latestRuns.columns.errors"),
                        render: (item) => item.errors_count,
                      },
                      {
                        key: "repriced",
                        label: t("latestRuns.columns.repriced"),
                        render: (item) => item.repriced_products,
                      },
                    ]}
                  />
                </div>
              </section>
            </div>

            {data.requires_operator_attention && data.requires_operator_attention.length > 0 ? (
              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("attention.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("attention.subtitle")}
                </p>
                <div className="mt-3">
                  <BackofficeTable
                    emptyLabel={t("states.empty")}
                    rows={data.requires_operator_attention}
                    columns={[
                      { key: "source", label: t("attention.columns.source"), render: (item) => item.source_code },
                      { key: "status", label: t("attention.columns.status"), render: (item) => <StatusChip status={item.status} /> },
                      { key: "matchRate", label: t("attention.columns.matchRate"), render: (item) => `${item.match_rate}%` },
                      { key: "errorRate", label: t("attention.columns.errorRate"), render: (item) => `${item.error_rate}%` },
                    ]}
                  />
                </div>
              </section>
            ) : null}
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
