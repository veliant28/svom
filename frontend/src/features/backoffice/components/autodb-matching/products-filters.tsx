import { ListChecks, LoaderCircle, Play, Square } from "lucide-react";
import type { RefObject } from "react";

import { PercentStepper } from "@/features/backoffice/components/pricing/percent-stepper";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

import { surfaceStyle } from "./ui";

export type AutoDbMatchingProductsPageSize = 25 | 50 | 100;

export type AutoDbMatchingProductsFilterState = {
  q: string;
  supplier_code: "" | "gpl" | "utr";
  matching_status: string;
  tecdoc_status: "" | "tecdoc" | "non_tecdoc" | "unknown";
};

type Translator = (key: string, values?: Record<string, string | number>) => string;

function clampBatchSize(value: number): number {
  const numeric = Number.isFinite(value) ? Math.round(value) : 50;
  return Math.max(10, Math.min(1000, numeric));
}

const STATUS_OPTIONS = [
  "linked",
  "local_found",
  "needs_review",
  "new",
  "skipped_bad_article_source",
  "skipped_non_tecdoc",
] as const;

function humanizeStatus(value: string): string {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  return raw.replaceAll("_", " ");
}

function safeTranslate(t: Translator, key: string, fallback: string): string {
  try {
    return t(key as never);
  } catch {
    return fallback;
  }
}

export function AutoDbMatchingProductsFilters({
  t,
  filters,
  pageSize,
  pageSizeOptions,
  onFilterChange,
  onPageSizeChange,
  batchSize,
  onBatchSizeChange,
  onRunTecdocBatch,
  onStopTecdocBatch,
  isTecdocBatchRunning,
  isQuotaCooldownActive,
  isBatchSubmitting,
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  isBulkRunning,
  onToggleBulkActions,
  onRunBulkBatch,
}: {
  t: Translator;
  filters: AutoDbMatchingProductsFilterState;
  pageSize: AutoDbMatchingProductsPageSize;
  pageSizeOptions: readonly AutoDbMatchingProductsPageSize[];
  onFilterChange: <K extends keyof AutoDbMatchingProductsFilterState>(key: K, value: AutoDbMatchingProductsFilterState[K]) => void;
  onPageSizeChange: (value: AutoDbMatchingProductsPageSize) => void;
  batchSize: number;
  onBatchSizeChange: (value: number) => void;
  onRunTecdocBatch: () => void;
  onStopTecdocBatch: () => void;
  isTecdocBatchRunning: boolean;
  isQuotaCooldownActive: boolean;
  isBatchSubmitting: boolean;
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  isBulkRunning: boolean;
  onToggleBulkActions: () => void;
  onRunBulkBatch: () => void;
}) {
  const isBatchDisabled = isTecdocBatchRunning || isBatchSubmitting;
  const isBatchBusy = isTecdocBatchRunning || isBatchSubmitting;
  const isStopDisabled = !isTecdocBatchRunning || isBatchSubmitting;
  const isBulkDisabled = selectedCount <= 0 || isBulkRunning || isTecdocBatchRunning || isQuotaCooldownActive;
  return (
    <section className="mb-3 flex items-center gap-2">
      <div ref={bulkActionsRef} className="relative shrink-0">
        <BackofficeTooltip content={t("actions.bulkActions")} placement="top" tooltipClassName="whitespace-nowrap">
          <button
            type="button"
            aria-label={t("actions.bulkActions")}
            aria-haspopup="menu"
            aria-expanded={bulkActionsOpen}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
            style={surfaceStyle}
            onClick={onToggleBulkActions}
          >
            <ListChecks size={16} />
          </button>
        </BackofficeTooltip>
        {bulkActionsOpen ? (
          <div
            role="menu"
            className="absolute left-0 top-full z-30 mt-1 min-w-[220px] rounded-lg border p-1.5 shadow-xl"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <button
              type="button"
              role="menuitem"
              disabled={isBulkDisabled}
              className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700/40 disabled:opacity-50"
              onClick={onRunBulkBatch}
            >
              {t("actions.bulkRunBatch")}
            </button>
          </div>
        ) : null}
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">

        <input
          value={filters.q}
          onChange={(event) => onFilterChange("q", event.target.value)}
          placeholder={t("products.search")}
          className="h-10 w-[240px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
          style={surfaceStyle}
        />

        <select
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number(event.target.value) as AutoDbMatchingProductsPageSize)}
          className="h-10 rounded-md border px-3 text-sm shrink-0"
          style={surfaceStyle}
        >
          {pageSizeOptions.map((size) => (
            <option key={size} value={size}>
              {t("products.filters.perPage", { count: size })}
            </option>
          ))}
        </select>

        <select
          value={filters.supplier_code}
          onChange={(event) => onFilterChange("supplier_code", event.target.value as AutoDbMatchingProductsFilterState["supplier_code"])}
          className="h-10 w-[138px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("products.filters.allSuppliers")}</option>
          <option value="gpl">{t("products.filters.supplierGpl")}</option>
          <option value="utr">{t("products.filters.supplierUtr")}</option>
        </select>

        <select
          value={filters.matching_status}
          onChange={(event) => onFilterChange("matching_status", event.target.value)}
          className="h-10 w-[188px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("products.filters.allStatuses")}</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {safeTranslate(
                t,
                `status.matching.${status}`,
                safeTranslate(t, `status.matchingShort.${status}`, humanizeStatus(status)),
              )}
            </option>
          ))}
        </select>

        <select
          value={filters.tecdoc_status}
          onChange={(event) => onFilterChange("tecdoc_status", event.target.value as AutoDbMatchingProductsFilterState["tecdoc_status"])}
          className="h-10 w-[150px] rounded-md border px-2 text-sm shrink-0"
          style={surfaceStyle}
        >
          <option value="">{t("products.filters.allTecdoc")}</option>
          <option value="tecdoc">{t("filters.tecdocOnly")}</option>
          <option value="non_tecdoc">{t("filters.nonTecdocOnly")}</option>
          <option value="unknown">{t("filters.unknownReview")}</option>
        </select>

        <PercentStepper
          value={clampBatchSize(batchSize)}
          onChange={(next) => onBatchSizeChange(clampBatchSize(next))}
          min={10}
          max={1000}
          step={10}
          minusLabel={t("actions.batchSizeMinus")}
          plusLabel={t("actions.batchSizePlus")}
          inputLabel={t("actions.batchSizeInput")}
          suffix=""
          inputMode="numeric"
          integerOnly
          inputWidthClassName="w-14"
          containerClassName="shrink-0"
          disabled={isBatchDisabled}
        />

        <BackofficeTooltip content={t("actions.runTecdocBatch")} placement="top" align="center" wrapperClassName="inline-flex">
          <button
            type="button"
            aria-label={t("actions.runTecdocBatch")}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border shrink-0 disabled:cursor-not-allowed disabled:opacity-60"
            style={surfaceStyle}
            disabled={isBatchDisabled}
            onClick={onRunTecdocBatch}
          >
            {isBatchBusy ? <LoaderCircle size={16} className="animate-spin" /> : <Play size={16} />}
          </button>
        </BackofficeTooltip>

        <BackofficeTooltip content={t("actions.stopTecdocBatch")} placement="top" align="center" wrapperClassName="inline-flex">
          <button
            type="button"
            aria-label={t("actions.stopTecdocBatch")}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border shrink-0 disabled:cursor-not-allowed disabled:opacity-60"
            style={{ ...surfaceStyle, borderColor: "#ef4444", color: "#dc2626" }}
            disabled={isStopDisabled}
            onClick={onStopTecdocBatch}
          >
            {isStopDisabled ? <Square size={16} /> : <Square size={16} fill="currentColor" />}
          </button>
        </BackofficeTooltip>

      </div>

    </section>
  );
}
