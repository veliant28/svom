"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeSupplierRuns,
  runRepriceAfterImportAction,
} from "@/features/backoffice/api/backoffice-api";
import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import type { BackofficeImportRun } from "@/features/backoffice/types/backoffice";

export function SupplierImportRunsPage() {
  const tSuppliers = useTranslations("backoffice.suppliers");
  const tRuns = useTranslations("backoffice.importRuns");
  const tStatus = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const queryFn = useCallback((token: string) => getBackofficeSupplierRuns(token, activeCode), [activeCode]);
  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportRun[] }>(queryFn, [activeCode]);
  const baseRuns = useMemo(() => data?.results ?? [], [data?.results]);

  const runs = useMemo(() => {
    const query = q.trim().toLowerCase();
    return baseRuns.filter((item) => {
      if (statusFilter && item.status !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }

      return [item.source_code, item.source_name, item.status, item.trigger].some((value) => String(value ?? "").toLowerCase().includes(query));
    });
  }, [baseRuns, q, statusFilter]);

  const reprice = useCallback(
    async (runId: string) => {
      if (!token) {
        return;
      }

      try {
        const response = await runRepriceAfterImportAction(token, {
          run_id: runId,
          dispatch_async: false,
        });

        showSuccess(tRuns("actions.repriceDone", { mode: response.mode }));
        await refetch();
      } catch (error: unknown) {
        showApiError(error, tRuns("actions.repriceFailed"));
      }
    },
    [refetch, showApiError, showSuccess, tRuns, token],
  );

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="importRuns"
        settingsHref={hrefFor("/backoffice/suppliers")}
        importHref={hrefFor("/backoffice/suppliers/import")}
        importRunsHref={hrefFor("/backoffice/suppliers/import-runs")}
        importErrorsHref={hrefFor("/backoffice/suppliers/import-errors")}
        importQualityHref={hrefFor("/backoffice/suppliers/import-quality")}
        productsHref={hrefFor("/backoffice/suppliers/products")}
        brandsHref={hrefFor("/backoffice/suppliers/brands", "utr")}
        onRefresh={() => {
          void Promise.all([refreshWorkspaceScope(), refetch()]);
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
    [activeCode, hrefFor, refetch, refreshWorkspaceScope, tSuppliers],
  );

  const switcher = useMemo(
    () => (
      <SupplierCodeSwitcher
        activeCode={activeCode}
        onChange={setActiveCode}
        utrLabel={tUtr("label")}
        gplLabel={tGpl("label")}
        ariaLabel={tRuns("title")}
      />
    ),
    [activeCode, setActiveCode, tGpl, tRuns, tUtr],
  );

  return (
    <section>
      <PageHeader
        title={tRuns("title")}
        description={tRuns("subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={tRuns("filters.search")}
          className="h-9 min-w-[220px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{tRuns("filters.allStatuses")}</option>
          <option value="pending">{tStatus("statuses.pending")}</option>
          <option value="running">{tStatus("statuses.running")}</option>
          <option value="success">{tStatus("statuses.success")}</option>
          <option value="partial">{tStatus("statuses.partial")}</option>
          <option value="failed">{tStatus("statuses.failed")}</option>
        </select>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!runs.length} emptyLabel={tRuns("states.empty")}>
        <BackofficeTable
          emptyLabel={tRuns("states.empty")}
          rows={runs}
          columns={[
            {
              key: "source",
              label: tRuns("table.columns.source"),
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
              label: tRuns("table.columns.status"),
              render: (item) => <StatusChip status={item.status} />,
            },
            {
              key: "rows",
              label: tRuns("table.columns.rows"),
              render: (item) => item.processed_rows,
            },
            {
              key: "offers",
              label: tRuns("table.columns.offers"),
              render: (item) => `${item.offers_created}/${item.offers_updated}`,
            },
            {
              key: "errors",
              label: tRuns("table.columns.errors"),
              render: (item) => item.errors_count,
            },
            {
              key: "repriced",
              label: tRuns("table.columns.repriced"),
              render: (item) => item.repriced_products,
            },
            {
              key: "actions",
              label: tRuns("table.columns.actions"),
              render: (item) => (
                <button
                  type="button"
                  className="h-8 rounded-md border px-2 text-xs"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  onClick={() => {
                    void reprice(item.id);
                  }}
                >
                  {tRuns("actions.reprice")}
                </button>
              ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
