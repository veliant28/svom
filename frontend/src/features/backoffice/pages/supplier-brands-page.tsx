"use client";

import { useCallback, useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { getBackofficeCatalogBrands, importBackofficeUtrBrands } from "@/features/backoffice/api/backoffice-api";
import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeCatalogBrand } from "@/features/backoffice/types/backoffice";

export function SupplierBrandsPage() {
  const t = useTranslations("backoffice.suppliers");
  const tCommon = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const [lastImportSummary, setLastImportSummary] = useState<{
    total_received: number;
    created: number;
    updated: number;
  } | null>(null);
  const [query, setQuery] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [page, setPage] = useState(1);

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    token,
    workspace,
    suppliersLoading,
    workspaceLoading,
    suppliersError,
    workspaceError,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const brandsQueryFn = useCallback(
    (apiToken: string) => {
      if (activeCode !== "utr") {
        return Promise.resolve({ count: 0, results: [] as BackofficeCatalogBrand[] });
      }
      return getBackofficeCatalogBrands(apiToken, {
        imported_from: "utr",
        q: query,
        is_active: isActiveFilter,
        page,
      });
    },
    [activeCode, isActiveFilter, page, query],
  );
  const {
    data: brandsData,
    isLoading: brandsLoading,
    error: brandsError,
    refetch: refetchBrands,
  } = useBackofficeQuery<{ count: number; results: BackofficeCatalogBrand[] }>(brandsQueryFn, [activeCode, isActiveFilter, page, query]);

  const rows = activeCode === "utr" ? brandsData?.results ?? [] : [];
  const pagesCount = useMemo(() => {
    const total = brandsData?.count ?? 0;
    return Math.max(1, Math.ceil(total / 20));
  }, [brandsData?.count]);
  const receivedCount = lastImportSummary?.total_received ?? workspace?.utr.last_brands_import_count ?? 0;
  const importedCount = lastImportSummary
    ? lastImportSummary.created + lastImportSummary.updated
    : workspace?.utr.last_brands_import_count ?? 0;
  const lastImportedAt = formatBackofficeDate(workspace?.utr.last_brands_import_at);

  const runBrandsImport = useCallback(async () => {
    if (!token || activeCode !== "utr") {
      return;
    }

    try {
      const payload = await importBackofficeUtrBrands(token);
      setLastImportSummary({
        total_received: payload.summary.total_received,
        created: payload.summary.created,
        updated: payload.summary.updated,
      });
      showSuccess(
        tUtr("messages.brandsImportedSummary", {
          created: payload.summary.created,
          updated: payload.summary.updated,
          skipped: payload.summary.skipped,
          duplicate_in_payload: payload.summary.duplicate_in_payload,
          errors: payload.summary.errors,
        }),
      );
      await Promise.all([refreshWorkspaceScope(), refetchBrands()]);
    } catch (error: unknown) {
      showApiError(error, tUtr("messages.brandsImportFailed"));
    }
  }, [activeCode, refreshWorkspaceScope, refetchBrands, showApiError, showSuccess, tUtr, token]);

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="brands"
        settingsHref={hrefFor("/backoffice/suppliers")}
        importHref={hrefFor("/backoffice/suppliers/import")}
        importRunsHref={hrefFor("/backoffice/suppliers/import-runs")}
        importErrorsHref={hrefFor("/backoffice/suppliers/import-errors")}
        importQualityHref={hrefFor("/backoffice/suppliers/import-quality")}
        productsHref={hrefFor("/backoffice/suppliers/products")}
        brandsHref={hrefFor("/backoffice/suppliers/brands", "utr")}
        onRefresh={() => {
          void refreshWorkspaceScope();
        }}
        settingsLabel={t("actions.settings")}
        importLabel={t("actions.import")}
        importRunsLabel={t("actions.importRuns")}
        importErrorsLabel={t("actions.importErrors")}
        importQualityLabel={t("actions.importQuality")}
        productsLabel={t("actions.products")}
        brandsLabel={t("actions.brands")}
        refreshLabel={t("actions.refreshAll")}
      />
    ),
    [activeCode, hrefFor, refreshWorkspaceScope, t],
  );

  const switcher = useMemo(
    () => (
      <SupplierCodeSwitcher
        activeCode={activeCode}
        onChange={setActiveCode}
        utrLabel={tUtr("label")}
        gplLabel={tGpl("label")}
        ariaLabel={t("title")}
      />
    ),
    [activeCode, setActiveCode, t, tGpl, tUtr],
  );

  return (
    <section>
      <PageHeader
        title={t("brandsPage.title")}
        description={t("brandsPage.subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <AsyncState
        isLoading={suppliersLoading || workspaceLoading || (activeCode === "utr" && brandsLoading)}
        error={suppliersError || workspaceError || (activeCode === "utr" ? brandsError : null)}
        empty={!workspace}
        emptyLabel={t("states.emptyWorkspace")}
      >
        {workspace ? (
          activeCode !== "utr" ? (
            <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <h2 className="text-sm font-semibold">{t("brandsPage.onlyUtrTitle")}</h2>
              <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{t("brandsPage.onlyUtr")}</p>
            </article>
          ) : (
            <>
              <section className="mb-3 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="grid gap-2 sm:grid-cols-2 lg:max-w-3xl lg:grid-cols-3">
                  <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--muted)" }}>
                      {t("brandsPage.stats.received")}
                    </p>
                    <p className="mt-1 text-lg font-semibold">{receivedCount}</p>
                  </article>
                  <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--muted)" }}>
                      {t("brandsPage.stats.imported")}
                    </p>
                    <p className="mt-1 text-lg font-semibold">{importedCount}</p>
                  </article>
                  <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--muted)" }}>
                      {t("brandsPage.stats.lastImportAt")}
                    </p>
                    <p className="mt-1 text-sm font-semibold">{lastImportedAt}</p>
                  </article>
                </div>

                <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                  <input
                    value={query}
                    onChange={(event) => {
                      setQuery(event.target.value);
                      setPage(1);
                    }}
                    placeholder={t("brandsPage.filters.search")}
                    className="h-9 min-w-[260px] rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  />
                  <select
                    value={isActiveFilter}
                    onChange={(event) => {
                      setIsActiveFilter(event.target.value);
                      setPage(1);
                    }}
                    className="h-9 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  >
                    <option value="">{t("brandsPage.filters.all")}</option>
                    <option value="true">{t("brandsPage.filters.active")}</option>
                    <option value="false">{t("brandsPage.filters.inactive")}</option>
                  </select>
                  <button
                    type="button"
                    className="h-9 rounded-md border px-3 text-xs font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void runBrandsImport();
                    }}
                  >
                    {t("brandsPage.actions.import")}
                  </button>
                </div>
              </section>

              <BackofficeTable
                rows={rows}
                emptyLabel={t("brandsPage.states.empty")}
                columns={[
                  {
                    key: "name",
                    label: t("brandsPage.table.columns.name"),
                    render: (item) => <p className="font-semibold">{item.name}</p>,
                  },
                  {
                    key: "status",
                    label: t("brandsPage.table.columns.status"),
                    render: (item) => (
                      <BackofficeStatusChip tone={item.is_active ? "success" : "gray"} icon={item.is_active ? CheckCircle2 : XCircle}>
                        {item.is_active ? tCommon("statuses.active") : tCommon("statuses.inactive")}
                      </BackofficeStatusChip>
                    ),
                  },
                  {
                    key: "updatedAt",
                    label: t("brandsPage.table.columns.updated"),
                    render: (item) => formatBackofficeDate(item.updated_at),
                  },
                ]}
              />

              <div className="mt-3 flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
                <span>{t("brandsPage.pagination.total", { count: brandsData?.count ?? 0 })}</span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    disabled={page <= 1}
                    onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                  >
                    {t("brandsPage.pagination.prev")}
                  </button>
                  <span>{t("brandsPage.pagination.page", { current: page, total: pagesCount })}</span>
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    disabled={page >= pagesCount}
                    onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
                  >
                    {t("brandsPage.pagination.next")}
                  </button>
                </div>
              </div>
            </>
          )
        ) : null}
      </AsyncState>
    </section>
  );
}
