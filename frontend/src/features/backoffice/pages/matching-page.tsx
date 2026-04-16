"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeConflictOffers, getBackofficeMatchingSummary } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatCard } from "@/features/backoffice/components/widgets/stat-card";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { Link } from "@/i18n/navigation";

export function MatchingPage() {
  const t = useTranslations("backoffice.matching");

  const summaryQuery = useCallback((token: string) => getBackofficeMatchingSummary(token), []);
  const conflictsQuery = useCallback((token: string) => getBackofficeConflictOffers(token, { page_size: 8 }), []);

  const summary = useBackofficeQuery(summaryQuery);
  const conflicts = useBackofficeQuery(conflictsQuery);

  return (
    <section>
      <PageHeader title={t("title")} description={t("subtitle")} />

      <AsyncState
        isLoading={summary.isLoading}
        error={summary.error}
        empty={!summary.data}
        emptyLabel={t("states.empty")}
      >
        {summary.data ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard title={t("cards.unmatched")} value={summary.data.unmatched} />
            <StatCard title={t("cards.conflicts")} value={summary.data.conflicts} />
            <StatCard title={t("cards.autoMatched")} value={summary.data.auto_matched} />
            <StatCard title={t("cards.manuallyMatched")} value={summary.data.manually_matched} />
            <StatCard title={t("cards.ignored")} value={summary.data.ignored} />
          </div>
        ) : null}
      </AsyncState>

      <section className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">{t("latestConflicts.title")}</h2>
          <Link href="/backoffice/matching/conflicts" className="text-xs underline" style={{ color: "var(--muted)" }}>
            {t("latestConflicts.viewAll")}
          </Link>
        </div>

        <AsyncState
          isLoading={conflicts.isLoading}
          error={conflicts.error}
          empty={!conflicts.data || conflicts.data.results.length === 0}
          emptyLabel={t("states.noConflicts")}
        >
          <BackofficeTable
            emptyLabel={t("states.noConflicts")}
            rows={conflicts.data?.results ?? []}
            columns={[
              {
                key: "supplier",
                label: t("table.columns.supplier"),
                render: (item) => item.supplier_code,
              },
              {
                key: "article",
                label: t("table.columns.article"),
                render: (item) => item.article || item.external_sku,
              },
              {
                key: "reason",
                label: t("table.columns.reason"),
                render: (item) => <StatusChip status={item.match_reason || item.match_status} />,
              },
              {
                key: "review",
                label: t("table.columns.review"),
                render: (item) => (
                  <Link href={`/backoffice/matching/review/${item.id}`} className="text-xs underline" style={{ color: "var(--muted)" }}>
                    {t("table.actions.open")}
                  </Link>
                ),
              },
            ]}
          />
        </AsyncState>
      </section>
    </section>
  );
}
