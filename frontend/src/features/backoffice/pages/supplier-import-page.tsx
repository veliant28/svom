"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  deleteBackofficeSupplierPriceList,
  downloadBackofficeSupplierPriceList,
  getBackofficeSupplierPriceListParams,
  getBackofficeSupplierPriceLists,
  importBackofficeSupplierPriceListToRaw,
  requestBackofficeSupplierPriceList,
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
import { formatBackofficeDate, formatSupplierError } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeSupplierPriceList } from "@/features/backoffice/types/backoffice";

const CHIP_BACKGROUND = [
  "color-mix(in srgb, var(--surface) 72%, #2563eb 28%)",
  "color-mix(in srgb, var(--surface) 72%, #16a34a 28%)",
  "color-mix(in srgb, var(--surface) 72%, #f59e0b 28%)",
  "color-mix(in srgb, var(--surface) 72%, #db2777 28%)",
  "color-mix(in srgb, var(--surface) 72%, #7c3aed 28%)",
];

type UtrFilterMode = "all" | "brands" | "categories" | "models";

function parseCsvStrings(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  );
}

function asNumberList(values: Array<number | string>): number[] {
  return Array.from(
    new Set(
      values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0),
    ),
  );
}

function asStringList(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter((value) => value.length > 0)));
}

function resolveParamsSourceLabel(source: string | undefined, t: ReturnType<typeof useTranslations>) {
  if (source === "utr_api") {
    return t("priceLifecycle.params.source.utr_api");
  }
  if (source === "gpl_api") {
    return t("priceLifecycle.params.source.gpl_api");
  }
  return t("priceLifecycle.params.source.fallback");
}

export function SupplierImportPage() {
  const t = useTranslations("backoffice.suppliers");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const tErrors = useTranslations("backoffice.errors");
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    token,
    suppliers,
    workspace,
    suppliersLoading,
    workspaceLoading,
    suppliersError,
    workspaceError,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const [format, setFormat] = useState("xlsx");
  const [inStockOnly, setInStockOnly] = useState(true);
  const [showScancode, setShowScancode] = useState(false);
  const [utrArticle, setUtrArticle] = useState(activeCode === "utr");
  const [utrFilterMode, setUtrFilterMode] = useState<UtrFilterMode>("all");
  const [selectedVisibleBrands, setSelectedVisibleBrands] = useState<number[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [manualModels, setManualModels] = useState("");
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const paramsQuery = useCallback(
    (apiToken: string) => getBackofficeSupplierPriceListParams(apiToken, activeCode),
    [activeCode],
  );
  const {
    data: supplierParams,
    refetch: refetchSupplierParams,
  } = useBackofficeQuery(paramsQuery, [activeCode]);

  const priceListsQuery = useCallback(
    (apiToken: string) => getBackofficeSupplierPriceLists(apiToken, activeCode),
    [activeCode],
  );
  const {
    data: priceListsData,
    isLoading: priceListsLoading,
    error: priceListsError,
    refetch: refetchPriceLists,
  } = useBackofficeQuery<{ count: number; results: BackofficeSupplierPriceList[] }>(priceListsQuery, [activeCode]);

  const refreshWorkspaceAndParams = useCallback(async () => {
    await Promise.all([refreshWorkspaceScope(), refetchSupplierParams()]);
  }, [refetchSupplierParams, refreshWorkspaceScope]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshWorkspaceAndParams(), refetchPriceLists()]);
  }, [refetchPriceLists, refreshWorkspaceAndParams]);

  const tokenReady = isHydrated && Boolean(token);

  const runAction = useCallback(
    async <T,>(
      action: () => Promise<T>,
      options: {
        successMessage: string;
        errorFallback?: string;
        refreshPriceLists?: boolean;
      },
    ) => {
      try {
        await action();
        showSuccess(options.successMessage);
        if (options.refreshPriceLists) {
          await Promise.all([refreshWorkspaceAndParams(), refetchPriceLists()]);
        } else {
          await refreshWorkspaceAndParams();
        }
      } catch (error: unknown) {
        showApiError(error, options.errorFallback ?? tErrors("actions.failed"));
      }
    },
    [refetchPriceLists, refreshWorkspaceAndParams, showApiError, showSuccess, tErrors],
  );

  const toggleVisibleBrand = useCallback((id: number) => {
    setSelectedVisibleBrands((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);
  const toggleCategory = useCallback((id: string) => {
    setSelectedCategories((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);
  const toggleModel = useCallback((name: string) => {
    setSelectedModels((prev) => (prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]));
  }, []);

  const rows = priceListsData?.results ?? [];
  const formats = supplierParams?.formats?.length ? supplierParams.formats : ["xlsx", "csv", "txt"];
  const formatOptions = supplierParams?.format_options?.length
    ? supplierParams.format_options
    : formats.map((item) => ({ format: item, caption: item }));
  const isUtr = activeCode === "utr";

  useEffect(() => {
    if (!supplierParams) {
      return;
    }
    if (supplierParams.defaults?.format) {
      setFormat(supplierParams.defaults.format);
    }
    setInStockOnly(Boolean(supplierParams.defaults?.in_stock));
    setShowScancode(Boolean(supplierParams.defaults?.show_scancode));
    setUtrArticle(Boolean(supplierParams.defaults?.utr_article));
  }, [supplierParams]);
  useEffect(() => {
    setUtrFilterMode("all");
    setSelectedVisibleBrands([]);
    setSelectedCategories([]);
    setSelectedModels([]);
    setUtrArticle(activeCode === "utr");
    setManualModels("");
  }, [activeCode]);
  useEffect(() => {
    if (!isUtr || supplierParams?.source !== "utr_api") {
      setSelectedVisibleBrands([]);
      setSelectedCategories([]);
      setSelectedModels([]);
      return;
    }

    if (utrFilterMode === "brands") {
      setSelectedVisibleBrands(
        Array.from(
          new Set(
            (supplierParams.visible_brands ?? [])
              .map((item) => Number(item.id))
              .filter((value) => Number.isFinite(value) && value > 0),
          ),
        ),
      );
      setSelectedCategories([]);
      setSelectedModels([]);
      setManualModels("");
      return;
    }
    if (utrFilterMode === "categories") {
      setSelectedCategories(
        asStringList(
          (supplierParams.categories ?? [])
            .map((item) => item.id?.trim())
            .filter((value): value is string => Boolean(value)),
        ),
      );
      setSelectedVisibleBrands([]);
      setSelectedModels([]);
      setManualModels("");
      return;
    }
    if (utrFilterMode === "models") {
      setSelectedModels(
        asStringList(
          (supplierParams.models ?? [])
            .map((item) => item.name?.trim())
            .filter((value): value is string => Boolean(value)),
        ),
      );
      setSelectedVisibleBrands([]);
      setSelectedCategories([]);
      return;
    }

    setSelectedVisibleBrands([]);
    setSelectedCategories([]);
    setSelectedModels([]);
    setManualModels("");
  }, [isUtr, supplierParams, utrFilterMode]);

  const effectiveVisibleBrands = useMemo(() => {
    if (!isUtr || utrFilterMode !== "brands") {
      return [];
    }
    return selectedVisibleBrands;
  }, [isUtr, selectedVisibleBrands, utrFilterMode]);
  const effectiveCategories = useMemo(() => {
    if (!isUtr || utrFilterMode !== "categories") {
      return [];
    }
    return selectedCategories;
  }, [isUtr, selectedCategories, utrFilterMode]);
  const effectiveModels = useMemo(() => {
    if (!isUtr || utrFilterMode !== "models") {
      return [];
    }
    return asStringList([...selectedModels, ...parseCsvStrings(manualModels)]);
  }, [isUtr, manualModels, selectedModels, utrFilterMode]);

  const requestPayload = useMemo(
    () => ({
      format,
      in_stock: inStockOnly,
      show_scancode: isUtr ? showScancode : false,
      utr_article: isUtr ? utrArticle : false,
      visible_brands: effectiveVisibleBrands,
      categories: effectiveCategories,
      models_filter: effectiveModels,
    }),
    [effectiveCategories, effectiveModels, effectiveVisibleBrands, format, inStockOnly, isUtr, showScancode, utrArticle],
  );
  const latestPriceList = rows[0];
  const latestDownloaded = rows.find((item) => Boolean(item.downloaded_at));
  const latestImported = rows.find((item) => Boolean(item.imported_at));
  const latestErrored = rows.find((item) => Boolean(item.last_error_message));
  const firstDownloadable = rows.find((item) => item.download_available);
  const firstImportable = rows.find((item) => item.import_available);

  const cooldownCanRun = workspace?.cooldown.can_run ?? true;
  const cooldownWaitSeconds = workspace?.cooldown.wait_seconds ?? 0;
  const [cooldownSecondsLeft, setCooldownSecondsLeft] = useState(Math.max(0, Math.floor(cooldownWaitSeconds)));

  useEffect(() => {
    setCooldownSecondsLeft(Math.max(0, Math.floor(cooldownWaitSeconds)));
  }, [cooldownWaitSeconds]);

  useEffect(() => {
    if (!isUtr || cooldownCanRun || cooldownSecondsLeft <= 0) {
      return;
    }

    const timer = window.setInterval(() => {
      setCooldownSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [cooldownCanRun, cooldownSecondsLeft, isUtr]);

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="import"
        settingsHref={hrefFor("/backoffice/suppliers")}
        importHref={hrefFor("/backoffice/suppliers/import")}
        importRunsHref={hrefFor("/backoffice/suppliers/import-runs")}
        importErrorsHref={hrefFor("/backoffice/suppliers/import-errors")}
        importQualityHref={hrefFor("/backoffice/suppliers/import-quality")}
        productsHref={hrefFor("/backoffice/suppliers/products")}
        brandsHref={hrefFor("/backoffice/suppliers/brands", "utr")}
        onRefresh={() => {
          void refreshAll();
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
    [activeCode, hrefFor, refreshAll, t],
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
        title={t("importPage.title")}
        description={t("importPage.subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <AsyncState
        isLoading={suppliersLoading || workspaceLoading}
        error={suppliersError || workspaceError}
        empty={!workspace}
        emptyLabel={t("states.emptyWorkspace")}
      >
        {workspace ? (
          <div className="grid gap-4">
            <section className="grid gap-4 lg:grid-cols-2">
              <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("priceLifecycle.operations.title")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("priceLifecycle.operations.subtitle")}</p>

                <div className="mt-3 flex flex-wrap items-end gap-2">
                  <button
                    type="button"
                    className="h-10 cursor-pointer rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    disabled={!tokenReady || !cooldownCanRun}
                    onClick={() => {
                      if (!tokenReady || !token) {
                        return;
                      }
                      void runAction(
                        () => requestBackofficeSupplierPriceList(token, activeCode, requestPayload),
                        {
                          successMessage: t("priceLifecycle.messages.requested"),
                          errorFallback: t("priceLifecycle.messages.requestFailed"),
                        },
                      );
                    }}
                  >
                    {t("priceLifecycle.actions.request")}
                  </button>

                  <button
                    type="button"
                    className="h-10 cursor-pointer rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    disabled={!tokenReady || !firstDownloadable}
                    onClick={() => {
                      if (!tokenReady || !token || !firstDownloadable) {
                        return;
                      }
                      void runAction(
                        () => downloadBackofficeSupplierPriceList(token, activeCode, firstDownloadable.id),
                        {
                          successMessage: t("priceLifecycle.messages.downloaded"),
                          errorFallback: t("priceLifecycle.messages.downloadFailed"),
                        },
                      );
                    }}
                  >
                    {t("priceLifecycle.actions.download")}
                  </button>

                  <button
                    type="button"
                    className="h-10 cursor-pointer rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    disabled={!tokenReady || !firstImportable}
                    onClick={() => {
                      if (!tokenReady || !token || !firstImportable) {
                        return;
                      }
                      void runAction(
                        () => importBackofficeSupplierPriceListToRaw(token, activeCode, firstImportable.id),
                        {
                          successMessage: t("priceLifecycle.messages.imported"),
                          errorFallback: t("priceLifecycle.messages.importFailed"),
                        },
                      );
                    }}
                  >
                    {t("priceLifecycle.actions.import")}
                  </button>

                  <select
                    value={format}
                    onChange={(event) => setFormat(event.target.value)}
                    aria-label={t("priceLifecycle.params.format")}
                    title={t("priceLifecycle.params.format")}
                    className="h-10 min-w-[12rem] cursor-pointer rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  >
                    {formatOptions.map((itemFormat) => (
                      <option key={itemFormat.format} value={itemFormat.format}>
                        {itemFormat.caption || itemFormat.format}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {supplierParams?.supports?.in_stock ? (
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      <input
                        type="checkbox"
                        checked={inStockOnly}
                        onChange={(event) => setInStockOnly(event.target.checked)}
                      />
                      {t("priceLifecycle.params.inStockOnly")}
                    </label>
                  ) : null}
                  {supplierParams?.supports?.show_scancode ? (
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      <input
                        type="checkbox"
                        checked={showScancode}
                        onChange={(event) => setShowScancode(event.target.checked)}
                      />
                      {t("priceLifecycle.params.showScancode")}
                    </label>
                  ) : null}
                  {supplierParams?.supports?.utr_article ? (
                    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      <input
                        type="checkbox"
                        checked={utrArticle}
                        onChange={(event) => setUtrArticle(event.target.checked)}
                      />
                      {t("priceLifecycle.params.utrArticle")}
                    </label>
                  ) : null}
                </div>

                <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  {resolveParamsSourceLabel(supplierParams?.source, t)}
                </p>

                {supplierParams?.source === "utr_api" ? (
                  <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                    {t("priceLifecycle.params.dynamicHint", {
                      brands: supplierParams.visible_brands_count,
                      categories: supplierParams.categories_count,
                      models: supplierParams.models_count,
                    })}
                  </p>
                ) : null}

                {isUtr && supplierParams?.source === "utr_api" ? (
                  <div className="mt-3 rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <div className="grid gap-2 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center">
                      <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.params.filterMode")}</p>
                      <select
                        value={utrFilterMode}
                        onChange={(event) => setUtrFilterMode(event.target.value as UtrFilterMode)}
                        className="h-9 rounded-md border px-2 text-xs"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      >
                        <option value="all">{t("priceLifecycle.params.filterNone")}</option>
                        <option value="brands">{t("priceLifecycle.params.filterBrands")}</option>
                        <option value="categories">{t("priceLifecycle.params.filterCategories")}</option>
                        <option value="models">{t("priceLifecycle.params.filterModels")}</option>
                      </select>
                    </div>

                    {utrFilterMode === "brands" ? (
                      <div className="mt-3 space-y-2">
                        <div className="flex max-h-36 flex-wrap gap-1 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
                          {(supplierParams.visible_brands ?? []).map((item) => {
                            const id = Number(item.id);
                            if (!Number.isFinite(id) || id <= 0) {
                              return null;
                            }
                            const isActive = selectedVisibleBrands.includes(id);
                            return (
                              <button
                                key={`brand-${id}`}
                                type="button"
                                className="cursor-pointer rounded-full border px-2 py-1 text-[11px] font-semibold"
                                style={{
                                  borderColor: "var(--border)",
                                  backgroundColor: isActive ? CHIP_BACKGROUND[0] : "var(--surface)",
                                }}
                                onClick={() => toggleVisibleBrand(id)}
                                title={`#${id} ${item.title}`}
                              >
                                {item.title || `#${id}`}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}

                    {utrFilterMode === "categories" ? (
                      <div className="mt-3 space-y-2">
                        <div className="flex max-h-36 flex-wrap gap-1 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
                          {(supplierParams.categories ?? []).map((item) => {
                            const id = item.id?.trim();
                            if (!id) {
                              return null;
                            }
                            const isActive = selectedCategories.includes(id);
                            return (
                              <button
                                key={`category-${id}`}
                                type="button"
                                className="cursor-pointer rounded-full border px-2 py-1 text-[11px] font-semibold"
                                style={{
                                  borderColor: "var(--border)",
                                  backgroundColor: isActive ? CHIP_BACKGROUND[1] : "var(--surface)",
                                }}
                                onClick={() => toggleCategory(id)}
                                title={`${id} ${item.title}`}
                              >
                                {item.title || id}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}

                    {utrFilterMode === "models" ? (
                      <div className="mt-3 space-y-2">
                        <div className="flex max-h-36 flex-wrap gap-1 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
                          {(supplierParams.models ?? []).map((item) => {
                            const name = item.name?.trim();
                            if (!name) {
                              return null;
                            }
                            const isActive = selectedModels.includes(name);
                            return (
                              <button
                                key={`model-${name}`}
                                type="button"
                                className="cursor-pointer rounded-full border px-2 py-1 text-[11px] font-semibold"
                                style={{
                                  borderColor: "var(--border)",
                                  backgroundColor: isActive ? CHIP_BACKGROUND[2] : "var(--surface)",
                                }}
                                onClick={() => toggleModel(name)}
                                title={name}
                              >
                                {name}
                              </button>
                            );
                          })}
                        </div>
                        <input
                          value={manualModels}
                          onChange={(event) => setManualModels(event.target.value)}
                          placeholder={t("priceLifecycle.params.manualPlaceholderModels")}
                          className="h-9 w-full rounded-md border px-2 text-xs"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        />
                      </div>
                    ) : null}

                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                        {t("priceLifecycle.params.filterOneOfRule")}
                      </p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>
                        {t("priceLifecycle.params.selectedCount", {
                          count: effectiveVisibleBrands.length + effectiveCategories.length + effectiveModels.length,
                        })}
                      </p>
                    </div>

                    {(supplierParams.visible_brands_truncated || supplierParams.categories_truncated || supplierParams.models_truncated) ? (
                      <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                        {t("priceLifecycle.params.truncatedHint")}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
                  {activeCode === "utr"
                    ? t("priceLifecycle.notes.utrGeneration")
                    : t("priceLifecycle.notes.gplReady")}
                </p>
              </article>

              <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold">{t("priceLifecycle.state.title")}</h2>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.subtitle")}</p>
                  </div>
                  <StatusChip
                    status={latestPriceList?.status || "pending"}
                    countdownSeconds={latestPriceList?.generation_wait_seconds}
                  />
                </div>

                <div className="mt-3 overflow-hidden rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <div className="grid gap-1.5 px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center">
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastRequestStatus")}</p>
                    <p className="text-sm font-semibold">
                      {latestPriceList ? (
                        <StatusChip
                          status={latestPriceList.status}
                          countdownSeconds={latestPriceList.generation_wait_seconds}
                        />
                      ) : "-"}
                    </p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.generation")}</p>
                    <p className="text-sm font-semibold">
                      {latestPriceList?.status === "generating"
                        ? t("priceLifecycle.state.generatingWait", { seconds: latestPriceList.generation_wait_seconds })
                        : t("priceLifecycle.state.generationDone")}
                    </p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.downloadAvailable")}</p>
                    <p className="text-sm font-semibold">
                      {latestPriceList?.download_available ? t("priceLifecycle.state.yes") : t("priceLifecycle.state.no")}
                    </p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastDownloaded")}</p>
                    <p className="text-sm font-semibold">{formatBackofficeDate(latestDownloaded?.downloaded_at)}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastImported")}</p>
                    <p className="text-sm font-semibold">{formatBackofficeDate(latestImported?.imported_at)}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
                      {isUtr ? t("priceLifecycle.state.cooldownUtr") : t("priceLifecycle.state.cooldownNotApplicableLabel")}
                    </p>
                    <p className="text-sm font-semibold">
                      {isUtr
                        ? (cooldownCanRun
                          ? t("priceLifecycle.state.cooldownReady")
                          : t("priceLifecycle.state.cooldownWait", { seconds: cooldownSecondsLeft }))
                        : t("priceLifecycle.state.cooldownNotApplicableValue")}
                    </p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastError")}</p>
                    <p className="text-sm font-semibold">
                      {formatSupplierError(
                        latestErrored?.last_error_message || workspace.import.last_import_error_message,
                        tErrors("actions.failed"),
                      )}
                    </p>
                  </div>
                </div>

              </article>
            </section>

            <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold">{t("priceLifecycle.table.title")}</h2>
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("priceLifecycle.table.subtitle")}</p>
                </div>
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  onClick={() => {
                    void refetchPriceLists();
                  }}
                  disabled={priceListsLoading}
                >
                  <RefreshCw
                    size={16}
                    className="animate-spin"
                    style={{ animationDuration: priceListsLoading ? "0.9s" : "2.2s" }}
                  />
                  {t("actions.refreshAll")}
                </button>
              </div>

              <div className="mt-3">
                <AsyncState
                  isLoading={priceListsLoading}
                  error={priceListsError}
                  empty={!rows.length}
                  emptyLabel={t("priceLifecycle.table.empty")}
                >
                  <BackofficeTable
                    emptyLabel={t("priceLifecycle.table.empty")}
                    rows={rows}
                    columns={[
                      {
                        key: "file",
                        label: t("priceLifecycle.table.columns.file"),
                        className: "min-w-[230px]",
                        render: (item) => (
                          <div className="space-y-1">
                            <p className="font-semibold">{item.source_file_name || "-"}</p>
                            <p className="text-xs" style={{ color: "var(--muted)" }}>
                              {item.remote_id ? `ID ${item.remote_id}` : "-"}
                            </p>
                          </div>
                        ),
                      },
                      {
                        key: "requested",
                        label: t("priceLifecycle.table.columns.requested"),
                        className: "min-w-[140px]",
                        render: (item) => formatBackofficeDate(item.requested_at),
                      },
                      {
                        key: "status",
                        label: t("priceLifecycle.table.columns.status"),
                        className: "min-w-[180px]",
                        render: (item) => (
                          <StatusChip
                            status={item.status}
                            countdownSeconds={item.generation_wait_seconds}
                          />
                        ),
                      },
                      {
                        key: "params",
                        label: t("priceLifecycle.table.columns.params"),
                        className: "min-w-[280px]",
                        render: (item) => {
                          const isGplRow = item.supplier_code === "gpl";

                          return (
                            <div className="space-y-1.5 text-xs">
                              <p>{t("priceLifecycle.table.paramFormat", { format: item.requested_format || "-" })}</p>
                              {isGplRow ? (
                                <div className="relative isolate flex items-center gap-5 whitespace-nowrap">
                                  <span className="group relative inline-flex items-center gap-1.5">
                                    <span style={{ color: "var(--muted)" }}>{`${t("priceLifecycle.table.columns.prices")}:`}</span>
                                    <button
                                      type="button"
                                      className="cursor-help rounded border px-1.5 py-0.5 text-xs font-semibold"
                                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                                      aria-label={item.price_columns.length ? item.price_columns.join(", ") : "-"}
                                    >
                                      {item.price_columns.length}
                                    </button>
                                    <span
                                      role="tooltip"
                                      className="pointer-events-none absolute bottom-full left-0 z-[220] mb-1.5 hidden min-w-[220px] max-w-[420px] whitespace-normal break-words rounded-md border px-2 py-1.5 text-[11px] shadow-lg group-hover:block group-focus-within:block"
                                      style={{
                                        borderColor: "color-mix(in srgb, var(--border) 82%, #0f172a 18%)",
                                        backgroundColor: "var(--surface)",
                                        color: "var(--text)",
                                      }}
                                    >
                                      {item.price_columns.length ? item.price_columns.join(", ") : "-"}
                                    </span>
                                  </span>
                                  <span className="group relative inline-flex items-center gap-1.5">
                                    <span style={{ color: "var(--muted)" }}>{`${t("priceLifecycle.table.columns.warehouses")}:`}</span>
                                    <button
                                      type="button"
                                      className="cursor-help rounded border px-1.5 py-0.5 text-xs font-semibold"
                                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                                      aria-label={item.warehouse_columns.length ? item.warehouse_columns.join(", ") : "-"}
                                    >
                                      {item.warehouse_columns.length}
                                    </button>
                                    <span
                                      role="tooltip"
                                      className="pointer-events-none absolute bottom-full left-0 z-[220] mb-1.5 hidden min-w-[220px] max-w-[420px] whitespace-normal break-words rounded-md border px-2 py-1.5 text-[11px] shadow-lg group-hover:block group-focus-within:block"
                                      style={{
                                        borderColor: "color-mix(in srgb, var(--border) 82%, #0f172a 18%)",
                                        backgroundColor: "var(--surface)",
                                        color: "var(--text)",
                                      }}
                                    >
                                      {item.warehouse_columns.length ? item.warehouse_columns.join(", ") : "-"}
                                    </span>
                                  </span>
                                </div>
                              ) : (
                                <>
                                  <p>{item.is_in_stock ? t("priceLifecycle.table.paramInStock") : t("priceLifecycle.table.paramAll")}</p>
                                  <p>{item.show_scancode ? t("priceLifecycle.table.paramScancodeOn") : t("priceLifecycle.table.paramScancodeOff")}</p>
                                  {item.visible_brands.length ? (
                                    <p>{t("priceLifecycle.table.paramBrands", { count: item.visible_brands.length })}</p>
                                  ) : null}
                                  {item.categories.length ? (
                                    <p>{t("priceLifecycle.table.paramCategories", { count: item.categories.length })}</p>
                                  ) : null}
                                  {item.models_filter.length ? (
                                    <p>{t("priceLifecycle.table.paramModels", { count: item.models_filter.length })}</p>
                                  ) : null}
                                </>
                              )}
                            </div>
                          );
                        },
                      },
                      {
                        key: "rows",
                        label: t("priceLifecycle.table.columns.rows"),
                        className: "min-w-[110px]",
                        render: (item) => (
                          <div className="space-y-1 text-xs">
                            <p>{t("priceLifecycle.table.rowsValue", { count: item.row_count })}</p>
                            <p style={{ color: "var(--muted)" }}>{item.file_size_label || "-"}</p>
                          </div>
                        ),
                      },
                      {
                        key: "actions",
                        label: t("priceLifecycle.table.columns.actions"),
                        className: "min-w-[320px]",
                        render: (item) => (
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              className="h-8 cursor-pointer rounded-md border px-2 text-xs font-semibold disabled:cursor-not-allowed"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                              disabled={!tokenReady || !cooldownCanRun}
                              onClick={() => {
                                if (!tokenReady || !token) {
                                  return;
                                }
                                void runAction(
                                  () => requestBackofficeSupplierPriceList(token, activeCode, {
                                    format: item.requested_format || format,
                                    in_stock: item.is_in_stock,
                                    show_scancode: item.supplier_code === "utr" ? item.show_scancode : false,
                                    utr_article: item.utr_article,
                                    visible_brands: asNumberList(item.visible_brands),
                                    categories: asStringList(item.categories),
                                    models_filter: asStringList(item.models_filter),
                                  }),
                                  {
                                    successMessage: t("priceLifecycle.messages.requested"),
                                    errorFallback: t("priceLifecycle.messages.requestFailed"),
                                    refreshPriceLists: true,
                                  },
                                );
                              }}
                            >
                              {t("priceLifecycle.actions.request")}
                            </button>
                            <button
                              type="button"
                              className="h-8 cursor-pointer rounded-md border px-2 text-xs font-semibold disabled:cursor-not-allowed"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                              disabled={!tokenReady || !item.download_available}
                              onClick={() => {
                                if (!tokenReady || !token) {
                                  return;
                                }
                                void runAction(
                                  () => downloadBackofficeSupplierPriceList(token, activeCode, item.id),
                                  {
                                    successMessage: t("priceLifecycle.messages.downloaded"),
                                    errorFallback: t("priceLifecycle.messages.downloadFailed"),
                                    refreshPriceLists: true,
                                  },
                                );
                              }}
                            >
                              {t("priceLifecycle.actions.download")}
                            </button>
                            <button
                              type="button"
                              className="h-8 cursor-pointer rounded-md border px-2 text-xs font-semibold disabled:cursor-not-allowed"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                              disabled={!tokenReady || !item.import_available}
                              onClick={() => {
                                if (!tokenReady || !token) {
                                  return;
                                }
                                void runAction(
                                  () => importBackofficeSupplierPriceListToRaw(token, activeCode, item.id),
                                  {
                                    successMessage: t("priceLifecycle.messages.imported"),
                                    errorFallback: t("priceLifecycle.messages.importFailed"),
                                    refreshPriceLists: true,
                                  },
                                );
                              }}
                            >
                              {t("priceLifecycle.actions.import")}
                            </button>
                            <button
                              type="button"
                              className="h-8 cursor-pointer rounded-md border px-2 text-xs font-semibold disabled:cursor-not-allowed"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                              disabled={!tokenReady}
                              onClick={() => {
                                if (!tokenReady || !token) {
                                  return;
                                }
                                void (async () => {
                                  try {
                                    const result = await deleteBackofficeSupplierPriceList(token, activeCode, item.id);
                                    if (!result.deleted_remote && result.remote_delete_error) {
                                      showWarning(
                                        t("priceLifecycle.messages.deletedLocalOnly", {
                                          reason: result.remote_delete_error,
                                        }),
                                      );
                                    } else {
                                      showSuccess(t("priceLifecycle.messages.deleted"));
                                    }
                                    await Promise.all([refreshWorkspaceAndParams(), refetchPriceLists()]);
                                  } catch (error: unknown) {
                                    showApiError(error, t("priceLifecycle.messages.deleteFailed"));
                                  }
                                })();
                              }}
                            >
                              {t("priceLifecycle.actions.delete")}
                            </button>
                          </div>
                        ),
                      },
                    ]}
                  />
                </AsyncState>
              </div>
            </section>

            <p className="text-xs" style={{ color: "var(--muted)" }}>
              {t("footer.availableSuppliers", { count: suppliers?.length ?? 0 })}
            </p>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
