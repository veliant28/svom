"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeImportQualityCompare,
  getBackofficeImportQualityRuns,
} from "@/features/backoffice/api/backoffice-api";
import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import type {
  BackofficeImportQuality,
  BackofficeImportQualityComparison,
} from "@/features/backoffice/types/backoffice";

export function SupplierImportQualityPage() {
  const tSuppliers = useTranslations("backoffice.suppliers");
  const tQuality = useTranslations("backoffice.importQuality");
  const tCommon = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const [q, setQ] = useState("");
  const [requiresAttention, setRequiresAttention] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");

  const runsQuery = useCallback(
    (token: string) =>
      getBackofficeImportQualityRuns(token, {
        source: activeCode,
        requires_attention: requiresAttention,
        q,
      }),
    [activeCode, q, requiresAttention],
  );
  const compareQuery = useCallback(
    (token: string) => (selectedRunId ? getBackofficeImportQualityCompare(token, selectedRunId) : Promise.resolve(null)),
    [selectedRunId],
  );

  const runs = useBackofficeQuery<{ count: number; results: BackofficeImportQuality[] }>(runsQuery, [activeCode, q, requiresAttention]);
  const compare = useBackofficeQuery<BackofficeImportQualityComparison | null>(compareQuery, [selectedRunId]);
  const rows = runs.data?.results ?? [];

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="importQuality"
        settingsHref={hrefFor("/backoffice/suppliers")}
        importHref={hrefFor("/backoffice/suppliers/import")}
        importRunsHref={hrefFor("/backoffice/suppliers/import-runs")}
        importErrorsHref={hrefFor("/backoffice/suppliers/import-errors")}
        importQualityHref={hrefFor("/backoffice/suppliers/import-quality")}
        productsHref={hrefFor("/backoffice/suppliers/products")}
        brandsHref={hrefFor("/backoffice/suppliers/brands", "utr")}
        onRefresh={() => {
          void Promise.all([refreshWorkspaceScope(), runs.refetch()]);
        }}
        settingsLabel={tSuppliers("actions.settings")}
        importLabel={tSuppliers("actions.import")}
        importRunsLabel={tSuppliers("actions.importRuns")}
        importErrorsLabel={tSuppliers("actions.importErrors")}
        importQualityLabel={tSuppliers("actions.importQuality")}
        productsLabel={tSuppliers("actions.products")}
        brandsLabel={tSuppliers("actions.brands")}
        refreshLabel={tSuppliers("actions.refreshAll")}
      />
    ),
    [activeCode, hrefFor, refreshWorkspaceScope, runs, tSuppliers],
  );

  const switcher = useMemo(
    () => (
      <SupplierCodeSwitcher
        activeCode={activeCode}
        onChange={setActiveCode}
        utrLabel={tUtr("label")}
        gplLabel={tGpl("label")}
        ariaLabel={tQuality("title")}
      />
    ),
    [activeCode, setActiveCode, tGpl, tQuality, tUtr],
  );

  return (
    <section>
      <PageHeader
        title={tQuality("title")}
        description={tQuality("subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={tQuality("filters.search")}
          className="h-9 min-w-[220px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={requiresAttention}
          onChange={(event) => setRequiresAttention(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{tQuality("filters.allAttention")}</option>
          <option value="true">{tQuality("filters.attentionOnly")}</option>
          <option value="false">{tQuality("filters.noAttention")}</option>
        </select>
      </div>

      <AsyncState isLoading={runs.isLoading} error={runs.error} empty={!rows.length} emptyLabel={tQuality("states.emptyRuns")}>
        <BackofficeTable
          emptyLabel={tQuality("states.emptyRuns")}
          rows={rows}
          columns={[
            {
              key: "source",
              label: tQuality("table.columns.source"),
              render: (item) => item.source_code,
            },
            {
              key: "status",
              label: tQuality("table.columns.status"),
              render: (item) => <StatusChip status={item.status} />,
            },
            {
              key: "matchRate",
              label: tQuality("table.columns.matchRate"),
              render: (item) => `${item.match_rate}%`,
            },
            {
              key: "errorRate",
              label: tQuality("table.columns.errorRate"),
              render: (item) => `${item.error_rate}%`,
            },
            {
              key: "attention",
              label: tQuality("table.columns.attention"),
              render: (item) => <StatusChip status={item.requires_operator_attention ? "attention" : "ok"} />,
            },
            {
              key: "actions",
              label: tQuality("table.columns.actions"),
              render: (item) => (
                <button
                  type="button"
                  className="h-8 rounded-md border px-2 text-xs"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  onClick={() => setSelectedRunId(item.run_id)}
                >
                  {tQuality("actions.compare")}
                </button>
              ),
            },
          ]}
        />
      </AsyncState>

      {selectedRunId ? (
        <section className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <h2 className="text-sm font-semibold">{tQuality("comparison.title")}</h2>
          <AsyncState
            isLoading={compare.isLoading}
            error={compare.error}
            empty={!compare.data}
            emptyLabel={tQuality("comparison.empty")}
          >
            {compare.data ? (
              <div className="mt-3 grid gap-2 text-sm">
                <p>{tQuality("comparison.matchRateDelta")}: {compare.data.delta.match_rate}%</p>
                <p>{tQuality("comparison.errorRateDelta")}: {compare.data.delta.error_rate}%</p>
                <p>{tQuality("comparison.requiresAttention")}: {compare.data.requires_operator_attention ? tCommon("yes") : tCommon("no")}</p>
              </div>
            ) : null}
          </AsyncState>
        </section>
      ) : null}
    </section>
  );
}
