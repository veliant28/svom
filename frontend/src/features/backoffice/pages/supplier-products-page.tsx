"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BadgeDollarSign } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { getBackofficeRawOffers, publishBackofficeSupplierMappedProducts } from "@/features/backoffice/api/backoffice-api";
import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { SupplierCategoryMappingModal } from "@/features/backoffice/components/suppliers/supplier-category-mapping-modal";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeRawOffer } from "@/features/backoffice/types/backoffice";

const PRICE_CHIP_TONES: BackofficeStatusChipTone[] = ["blue", "success", "orange", "red", "info"];
const PAGE_SIZE_OPTIONS = [15, 25, 50, 100, 500] as const;

type PriceLevel = {
  key: string;
  value: string;
  badgeLabel: string;
  tone: BackofficeStatusChipTone;
  order: number;
  index: number;
};

function resolveGplPriceMeta(key: string): { badgeLabel: string; tone: BackofficeStatusChipTone; order: number } | null {
  const normalized = key.toLowerCase().replace(/[\s_-]/g, "");
  if (normalized.includes("ррц") || normalized.includes("rrc")) {
    return { badgeLabel: "РРЦ", tone: "blue", order: 1 };
  }
  if (normalized.includes("опт2") || normalized.includes("opt2")) {
    return { badgeLabel: "ОПТ2", tone: "success", order: 2 };
  }
  if (normalized.includes("опт4") || normalized.includes("opt4")) {
    return { badgeLabel: "ОПТ4", tone: "orange", order: 3 };
  }
  if (normalized.includes("опт10") || normalized.includes("opt10")) {
    return { badgeLabel: "ОПТ10", tone: "red", order: 4 };
  }
  return null;
}

function extractPriceLevels(payload: Record<string, unknown>, supplierCode: string): PriceLevel[] {
  const entries = Object.entries(payload);
  const result: PriceLevel[] = [];
  for (const [key, value] of entries) {
    const label = key.toLowerCase();
    const gplMeta = supplierCode === "gpl" ? resolveGplPriceMeta(key) : null;
    const isPriceLike = gplMeta !== null || label.includes("ціна") || label.includes("price") || label.includes("ррц") || label.includes("опт") || label.includes("opt");
    if (!isPriceLike) {
      continue;
    }
    const normalized = String(value ?? "").trim();
    if (!normalized) {
      continue;
    }
    if (supplierCode === "gpl") {
      result.push({
        key,
        value: normalized,
        badgeLabel: gplMeta?.badgeLabel ?? key,
        tone: gplMeta?.tone ?? "info",
        order: gplMeta?.order ?? 100 + result.length,
        index: result.length,
      });
      continue;
    }
    result.push({
      key,
      value: normalized,
      badgeLabel: key,
      tone: PRICE_CHIP_TONES[result.length % PRICE_CHIP_TONES.length],
      order: result.length,
      index: result.length,
    });
  }
  return result.sort((left, right) => {
    const orderCompare = left.order - right.order;
    if (orderCompare !== 0) {
      return orderCompare;
    }
    return left.index - right.index;
  });
}

function priceDigitsOnly(value: string): string {
  const numeric = value.replace(/[^\d.,-]/g, "").trim();
  return numeric || value;
}

type WarehouseSegment = {
  key: string;
  value: string;
  qty: number | null;
};

function warehouseVisualRank(qty: number | null): number {
  if (qty === null || !Number.isFinite(qty)) {
    return Number.MAX_SAFE_INTEGER;
  }
  if (qty >= 7) {
    return 1;
  }
  if (qty >= 4) {
    return 2;
  }
  if (qty >= 1) {
    return 3;
  }
  if (qty === 0) {
    return 4;
  }
  return Number.MAX_SAFE_INTEGER;
}

function extractWarehouses(payload: Record<string, unknown>): WarehouseSegment[] {
  const entries = Object.entries(payload);
  const result: Array<WarehouseSegment & { index: number }> = [];
  for (const [key, value] of entries) {
    const label = key.toLowerCase();
    const isWarehouse =
      label.includes("склад")
      || label.includes("warehouse")
      || label.includes("обл")
      || label.startsWith("count_warehouse_");
    if (!isWarehouse) {
      continue;
    }
    const normalized = String(value ?? "").trim();
    if (!normalized) {
      continue;
    }
    result.push({
      key,
      value: normalized,
      qty: parseWarehouseQty(normalized),
      index: result.length,
    });
  }

  return result
    .sort((left, right) => {
      const rankCompare = warehouseVisualRank(left.qty) - warehouseVisualRank(right.qty);
      if (rankCompare !== 0) {
        return rankCompare;
      }
      if (left.qty !== null && right.qty !== null) {
        const qtyCompare = right.qty - left.qty;
        if (qtyCompare !== 0) {
          return qtyCompare;
        }
      } else if (left.qty === null && right.qty !== null) {
        return 1;
      } else if (left.qty !== null && right.qty === null) {
        return -1;
      }
      return left.index - right.index;
    })
    .map(({ key, value, qty }) => ({ key, value, qty }));
}

function compactWarehouseName(key: string): string {
  const normalized = key
    .replace(/^count_warehouse_/i, "")
    .replace(/^warehouse[_\s-]*/i, "")
    .replace(/_/g, " ")
    .trim();

  if (!normalized) {
    return "Склад";
  }
  return normalized;
}

function parseWarehouseQty(value: string): number | null {
  const normalized = value
    .replace(",", ".")
    .replace(/[^\d.-]/g, "")
    .trim();
  if (!normalized) {
    return null;
  }
  const qty = Number(normalized);
  if (!Number.isFinite(qty)) {
    return null;
  }
  return qty;
}

function resolveWarehouseTone(qty: number | null): { border: string; background: string; text: string } {
  if (qty === 0) {
    return {
      border: "#94a3b8",
      background: "#94a3b8",
      text: "#ffffff",
    };
  }
  if (qty !== null && qty > 0 && qty <= 3) {
    return {
      border: "#e11d48",
      background: "#e11d48",
      text: "#ffffff",
    };
  }
  if (qty !== null && qty >= 4 && qty <= 6) {
    return {
      border: "#f59e0b",
      background: "#f59e0b",
      text: "#111827",
    };
  }
  if (qty !== null && qty >= 7) {
    return {
      border: "#16a34a",
      background: "#16a34a",
      text: "#ffffff",
    };
  }
  return {
    border: "var(--border)",
    background: "var(--surface-2)",
    text: "var(--text)",
  };
}

function formatWarehouseQty(qty: number | null): string {
  if (qty === null) {
    return "?";
  }
  const normalized = Math.max(0, Math.trunc(qty));
  if (normalized > 99) {
    return "99+";
  }
  return String(normalized);
}

export function SupplierProductsPage() {
  const t = useTranslations("backoffice.suppliers");
  const tCommon = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const locale = useLocale();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(25);
  const [isCategoryMappingOpen, setIsCategoryMappingOpen] = useState(false);
  const [selectedRawOfferId, setSelectedRawOfferId] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeRawOffers(token, {
        supplier: activeCode,
        q,
        locale,
        page,
        page_size: pageSize,
      }),
    [activeCode, locale, page, pageSize, q],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeRawOffer[] }>(queryFn, [activeCode, locale, page, pageSize, q]);
  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const pagesCount = useMemo(() => Math.max(1, Math.ceil(totalCount / pageSize)), [pageSize, totalCount]);

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="products"
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
    [activeCode, hrefFor, refetch, refreshWorkspaceScope, t],
  );

  const switcher = useMemo(
    () => (
      <SupplierCodeSwitcher
        activeCode={activeCode}
        onChange={(next) => {
          setActiveCode(next);
          setPage(1);
        }}
        utrLabel={tUtr("label")}
        gplLabel={tGpl("label")}
        ariaLabel={t("productsPage.title")}
      />
    ),
    [activeCode, setActiveCode, t, tGpl, tUtr],
  );

  const publishMapped = useCallback(async () => {
    if (!token || isPublishing) {
      return;
    }

    setIsPublishing(true);
    try {
      const payload = await publishBackofficeSupplierMappedProducts(token, activeCode, {
        include_needs_review: false,
        dry_run: false,
        reprice_after_publish: true,
      });
      const result = payload.result;
      showSuccess(
        t("productsPage.messages.publishSuccess", {
          matched: result.eligible_rows,
          created: result.created_rows,
          updated: result.updated_rows,
          skipped: result.skipped_rows,
          errors: result.error_rows,
        }),
      );
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("productsPage.messages.publishFailed"));
    } finally {
      setIsPublishing(false);
    }
  }, [activeCode, isPublishing, refetch, showApiError, showSuccess, t, token]);

  const publishDisabled = !isHydrated || !token || isPublishing;

  return (
    <section>
      <PageHeader
        title={t("productsPage.title")}
        description={t("productsPage.subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          placeholder={t("productsPage.search")}
          className="h-10 min-w-[260px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={String(pageSize)}
          onChange={(event) => {
            const nextSize = Number(event.target.value) as (typeof PAGE_SIZE_OPTIONS)[number];
            setPageSize(nextSize);
            setPage(1);
          }}
          className="h-10 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {PAGE_SIZE_OPTIONS.map((sizeOption) => (
            <option key={sizeOption} value={sizeOption}>
              {`${t("productsPage.pagination.perPage")}: ${sizeOption}`}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="h-10 rounded-md border px-3 text-sm font-semibold disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          disabled={publishDisabled}
          onClick={() => {
            void publishMapped();
          }}
        >
          {isPublishing ? tCommon("loading") : t("productsPage.actions.publishMapped")}
        </button>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("productsPage.empty")}>
        <BackofficeTable
          noHorizontalScroll
          emptyLabel={t("productsPage.empty")}
          rows={rows}
          columns={[
            {
              key: "sku",
              label: t("productsPage.table.columns.sku"),
              className: "w-[14%]",
              render: (item) => (
                <div>
                  <p className="truncate font-semibold" title={item.external_sku}>{item.external_sku}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>{item.article}</p>
                </div>
              ),
            },
            {
              key: "brand",
              label: t("productsPage.table.columns.brand"),
              className: "w-[9%]",
              render: (item) => item.brand_name || "-",
            },
            {
              key: "product",
              label: t("productsPage.table.columns.product"),
              className: "w-[17%]",
              render: (item) => {
                const productName = item.product_name || "-";
                return (
                  <BackofficeTooltip
                    content={productName}
                    placement="top"
                    align="start"
                    wrapperClassName="inline-flex max-w-full"
                    tooltipClassName="max-w-[320px]"
                  >
                    <span tabIndex={0} className="line-clamp-2 cursor-help">
                      {productName}
                    </span>
                  </BackofficeTooltip>
                );
              },
            },
            {
              key: "prices",
              label: t("productsPage.table.columns.prices"),
              className: "w-[15%]",
              render: (item) => {
                const levels = extractPriceLevels(item.raw_payload ?? {}, item.source_code);
                if (!levels.length) {
                  return <span>-</span>;
                }
                return (
                  <div className="grid grid-cols-2 gap-1">
                    {levels.slice(0, 6).map((level) => (
                      <BackofficeTooltip
                        key={`${item.id}-price-${level.key}`}
                        content={(
                          <span className="grid gap-1">
                            <span>
                              <span style={{ color: "var(--muted)" }}>{level.badgeLabel}:</span>{" "}
                              {priceDigitsOnly(level.value)}
                            </span>
                            <span>
                              <span style={{ color: "var(--muted)" }}>{t("productsPage.tooltip.updatedAt")}:</span>{" "}
                              {formatBackofficeDate(item.updated_at)}
                            </span>
                          </span>
                        )}
                        placement="top"
                        align="start"
                        wrapperClassName="inline-flex max-w-full"
                        tooltipClassName="min-w-[210px]"
                      >
                        <BackofficeStatusChip
                          tone={level.tone}
                          icon={BadgeDollarSign}
                          className="w-full max-w-full min-w-0 cursor-help justify-start overflow-hidden"
                        >
                          <span className="block min-w-0 truncate tabular-nums">
                            {priceDigitsOnly(level.value)}
                          </span>
                        </BackofficeStatusChip>
                      </BackofficeTooltip>
                    ))}
                  </div>
                );
              },
            },
            {
              key: "warehouses",
              label: t("productsPage.table.columns.warehouses"),
              className: "w-[32%]",
              render: (item) => {
                const warehouses = extractWarehouses(item.raw_payload ?? {});
                if (!warehouses.length) {
                  return <span>-</span>;
                }
                return (
                  <div className="max-w-full pb-0.5 pt-1">
                    <div
                      className="inline-flex max-w-full flex-wrap items-center gap-px rounded-[6px] border p-px"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    >
                      {warehouses.map((warehouse) => {
                        const tone = resolveWarehouseTone(warehouse.qty);
                        const supplierLabel =
                          item.source_code === "utr"
                            ? tUtr("label")
                            : item.source_code === "gpl"
                              ? tGpl("label")
                              : item.source_code.toUpperCase();
                        const warehouseLabel = compactWarehouseName(warehouse.key);
                        const qtyLabel = formatWarehouseQty(warehouse.qty);
                        return (
                          <BackofficeTooltip
                            key={`${item.id}-warehouse-${warehouse.key}`}
                            content={(
                              <span className="grid gap-1">
                                <span className="font-semibold">{supplierLabel}</span>
                                <span>
                                  <span style={{ color: "var(--muted)" }}>{t("productsPage.table.columns.warehouses")}:</span>{" "}
                                  {warehouseLabel}
                                </span>
                                <span>
                                  <span style={{ color: "var(--muted)" }}>{t("productsPage.table.columns.stock")}:</span>{" "}
                                  {warehouse.value}
                                </span>
                              </span>
                            )}
                            placement="top"
                            align="start"
                            wrapperClassName="inline-flex"
                            tooltipClassName="min-w-[190px]"
                          >
                            <button
                              type="button"
                              className="inline-flex h-6 min-w-6 cursor-pointer items-center justify-center rounded-[3px] border px-1 text-[11px] font-semibold leading-none"
                              style={{
                                borderColor: tone.border,
                                backgroundColor: tone.background,
                                color: tone.text,
                              }}
                              aria-label={`${warehouseLabel}, ${t("productsPage.table.columns.stock")}: ${warehouse.value}`}
                            >
                              {qtyLabel}
                            </button>
                          </BackofficeTooltip>
                        );
                      })}
                    </div>
                  </div>
                );
              },
            },
            {
              key: "state",
              label: t("productsPage.table.columns.state"),
              className: "w-[13%]",
              render: (item) => (
                <button
                  type="button"
                  className="inline-flex rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                  style={{ cursor: "pointer" }}
                  onClick={() => {
                    setSelectedRawOfferId(item.id);
                    setIsCategoryMappingOpen(true);
                  }}
                  aria-label={t("productsPage.categoryMapping.openBadgeAria")}
                  aria-haspopup="dialog"
                  aria-expanded={isCategoryMappingOpen && selectedRawOfferId === item.id}
                  title={item.mapped_category_path || t("productsPage.categoryMapping.states.notMapped")}
                >
                  <StatusChip status={item.category_mapping_status || "unmapped"} />
                </button>
              ),
            },
          ]}
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("productsPage.pagination.total", { count: totalCount })}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              {t("productsPage.pagination.prev")}
            </button>
            <span>{t("productsPage.pagination.page", { current: page, total: pagesCount })}</span>
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page >= pagesCount}
              onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
            >
              {t("productsPage.pagination.next")}
            </button>
          </div>
        </div>
      </AsyncState>

      <SupplierCategoryMappingModal
        isOpen={isCategoryMappingOpen}
        rawOfferId={selectedRawOfferId}
        token={token}
        locale={locale}
        onClose={() => {
          setIsCategoryMappingOpen(false);
          setSelectedRawOfferId(null);
        }}
        onSaved={refetch}
      />
    </section>
  );
}
