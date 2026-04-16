"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeSupplierErrors } from "@/features/backoffice/api/backoffice-api";
import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import type { BackofficeImportError } from "@/features/backoffice/types/backoffice";

export function SupplierImportErrorsPage() {
  const tSuppliers = useTranslations("backoffice.suppliers");
  const tErrors = useTranslations("backoffice.importErrors");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const [q, setQ] = useState("");

  const queryFn = useCallback((token: string) => getBackofficeSupplierErrors(token, activeCode), [activeCode]);
  const { data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportError[] }>(queryFn, [activeCode]);
  const baseErrors = data?.results ?? [];

  const errors = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) {
      return baseErrors;
    }

    return baseErrors.filter((item) =>
      [item.source_code, item.error_code, item.external_sku, item.message, item.run]
        .some((value) => String(value ?? "").toLowerCase().includes(query)),
    );
  }, [baseErrors, q]);

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="importErrors"
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
        ariaLabel={tErrors("title")}
      />
    ),
    [activeCode, setActiveCode, tErrors, tGpl, tUtr],
  );

  return (
    <section>
      <PageHeader
        title={tErrors("title")}
        description={tErrors("subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={tErrors("filters.search")}
          className="h-9 min-w-[220px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!errors.length} emptyLabel={tErrors("states.empty")}>
        <BackofficeTable
          emptyLabel={tErrors("states.empty")}
          rows={errors}
          columns={[
            {
              key: "source",
              label: tErrors("table.columns.source"),
              render: (item) => item.source_code,
            },
            {
              key: "errorCode",
              label: tErrors("table.columns.errorCode"),
              render: (item) => item.error_code || "-",
            },
            {
              key: "sku",
              label: tErrors("table.columns.sku"),
              render: (item) => item.external_sku || "-",
            },
            {
              key: "message",
              label: tErrors("table.columns.message"),
              render: (item) => (
                <p className="max-w-[440px] text-xs" title={item.message}>
                  {item.message}
                </p>
              ),
            },
            {
              key: "created",
              label: tErrors("table.columns.created"),
              render: (item) => new Date(item.created_at).toLocaleString(),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
