import { AlertTriangle, CheckCircle2, CircleHelp, Clock3, LoaderCircle, MinusCircle, Search, SearchCode, XCircle, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { BackofficeTable, type BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import type { AutoDbProductJob } from "@/features/backoffice/types/backoffice";

import { translateAutoDbReason } from "./reason-i18n";
import { formatDateTime, surfaceStyle } from "./ui";

type Translator = (key: string, values?: Record<string, string | number>) => string;

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

function normalizeReason(value: string): string {
  return String(value || "").trim();
}

function matchingStatusMeta(status: string): { tone: BackofficeStatusChipTone; icon: LucideIcon } {
  const key = String(status || "").trim().toLowerCase();
  const map: Record<string, { tone: BackofficeStatusChipTone; icon: LucideIcon }> = {
    new: { tone: "info", icon: Clock3 },
    local_found: { tone: "blue", icon: SearchCode },
    remote_pending: { tone: "blue", icon: LoaderCircle },
    remote_found: { tone: "blue", icon: Search },
    remote_found_exact: { tone: "success", icon: CheckCircle2 },
    remote_found_article_only: { tone: "warning", icon: Search },
    remote_found_local_clone: { tone: "teal", icon: SearchCode },
    remote_found_other: { tone: "blue", icon: Search },
    remote_not_found: { tone: "gray", icon: XCircle },
    quota_paused: { tone: "error", icon: AlertTriangle },
    clone_sync_ready: { tone: "orange", icon: Clock3 },
    clone_synced: { tone: "teal", icon: CheckCircle2 },
    safe_link_candidate: { tone: "success", icon: CheckCircle2 },
    linked: { tone: "success", icon: CheckCircle2 },
    needs_review: { tone: "warning", icon: AlertTriangle },
    rejected: { tone: "error", icon: XCircle },
    skipped_non_tecdoc: { tone: "warning", icon: AlertTriangle },
    skipped_brand_unresolved: { tone: "warning", icon: AlertTriangle },
    skipped_split_needed: { tone: "warning", icon: AlertTriangle },
    skipped_unsafe_ambiguous: { tone: "warning", icon: AlertTriangle },
    skipped_bad_article_source: { tone: "warning", icon: AlertTriangle },
  };
  return map[key] || { tone: "gray", icon: CircleHelp };
}

function tecdocStatusMeta(status: string): { tone: BackofficeStatusChipTone; icon: LucideIcon } {
  const key = String(status || "").trim().toLowerCase();
  if (key === "tecdoc") return { tone: "success", icon: CheckCircle2 };
  if (key === "non_tecdoc") return { tone: "gray", icon: MinusCircle };
  return { tone: "warning", icon: CircleHelp };
}

function supplierTone(code: string): BackofficeStatusChipTone {
  const normalized = String(code || "").trim().toLowerCase();
  if (normalized === "gpl") return "teal";
  if (normalized === "utr") return "blue";
  return "gray";
}

function supplierTooltipLabel(code: string): string {
  const normalized = String(code || "").trim().toLowerCase();
  if (normalized === "utr") return "Юник Трейд";
  if (normalized === "gpl") return "GPL";
  return normalized.toUpperCase();
}

export function AutoDbMatchingProductsTable({
  t,
  rows,
  isLoading,
  error,
  page,
  pagesCount,
  totalCount,
  selectedSet,
  allPageSelected,
  somePageSelected,
  onPageChange,
  onToggleSelectAllPage,
  onToggleSelected,
  onOpenDetails,
  onSearchProduct,
}: {
  t: Translator;
  rows: AutoDbProductJob[];
  isLoading: boolean;
  error: string | null;
  page: number;
  pagesCount: number;
  totalCount: number;
  selectedSet: Set<string>;
  allPageSelected: boolean;
  somePageSelected: boolean;
  onPageChange: (next: number) => void;
  onToggleSelectAllPage: () => void;
  onToggleSelected: (id: string) => void;
  onOpenDetails: (job: AutoDbProductJob) => void;
  onSearchProduct: (job: AutoDbProductJob) => void;
}) {
  const selectAllRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (!selectAllRef.current) return;
    selectAllRef.current.indeterminate = somePageSelected && !allPageSelected;
  }, [somePageSelected, allPageSelected]);

  const supplierBadges = (row: AutoDbProductJob): string[] => {
    const fromProduct = Array.isArray(row.product.supplier_codes) ? row.product.supplier_codes : [];
    const normalized = fromProduct
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean);
    if (normalized.length) {
      return [...new Set(normalized)];
    }
    const fallback = String(row.supplier_code || "").trim().toLowerCase();
    return fallback ? [fallback] : [];
  };

  const columns = useMemo<Array<BackofficeColumn<AutoDbProductJob>>>(() => [
    {
      key: "select",
      label: (
        <input
          ref={selectAllRef}
          type="checkbox"
          checked={allPageSelected}
          onChange={onToggleSelectAllPage}
          aria-label={t("actions.selectAll")}
        />
      ),
      className: "w-[34px]",
      render: (row) => (
        <input
          type="checkbox"
          checked={selectedSet.has(row.id)}
          onChange={() => onToggleSelected(row.id)}
          aria-label={t("actions.selectOne")}
        />
      ),
    },
    {
      key: "sku",
      label: t("products.columns.sku"),
      className: "w-[160px]",
      render: (row) => (
        <div className="min-w-0">
          <p className="font-semibold">{row.product.svom_sku || row.product.sku}</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>{row.product.sku}</p>
          <div className="mt-1 flex items-center gap-1 whitespace-nowrap overflow-x-auto">
            {supplierBadges(row).map((code) => (
              <BackofficeTooltip
                key={`${row.id}-${code}`}
                content={supplierTooltipLabel(code)}
                placement="top"
                align="center"
                wrapperClassName="inline-flex"
                tooltipClassName="whitespace-nowrap"
              >
                <BackofficeStatusChip
                  tone={supplierTone(code)}
                  className="cursor-pointer h-6 py-0 items-center [&>span]:leading-none"
                >
                  {code.toUpperCase()}
                </BackofficeStatusChip>
              </BackofficeTooltip>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: "name",
      label: t("products.columnsShort.name"),
      className: "w-[294px]",
      render: (row) => (
        <div className="min-w-0">
          <BackofficeTooltip
            content={row.product.name || "-"}
            placement="top"
            align="start"
            wrapperClassName="inline-flex max-w-full"
            tooltipClassName="max-w-[320px]"
          >
            <span tabIndex={0} className="block truncate cursor-help font-medium">
              {row.product.name || "-"}
            </span>
          </BackofficeTooltip>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{row.product.category || "-"}</p>
        </div>
      ),
    },
    {
      key: "brand",
      label: t("products.columns.brand"),
      className: "w-[110px]",
      render: (row) => (
        <p>{row.raw_brand || row.product.brand || "-"}</p>
      ),
    },
    {
      key: "autodb",
      label: t("products.columnsShort.autodb"),
      className: "w-[140px]",
      render: (row) => (
        <>
          <p>{row.autodb_supplier_display || "-"}</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>{row.autodb_supplier_id ?? "-"}</p>
        </>
      ),
    },
    {
      key: "article",
      label: t("products.columnsShort.article"),
      className: "w-[120px]",
      render: (row) => (
        <p className="font-medium">{row.canonical_article || row.article_value || "-"}</p>
      ),
    },
    {
      key: "status",
      label: t("products.columns.status"),
      className: "w-[124px]",
      render: (row) => {
        const matchingStatusKey = row.matching_status_view || row.matching_status;
        const matching = matchingStatusMeta(matchingStatusKey);
        const tecdoc = tecdocStatusMeta(row.tecdoc_status);
        const reasonRaw = normalizeReason(row.last_evidence.reason);
        const reasonText = translateAutoDbReason(t, reasonRaw);
        const evidenceTime = row.last_evidence.created_at || row.updated_at;
        const matchingLabel = safeTranslate(
          t,
          `status.matchingShort.${matchingStatusKey}`,
          safeTranslate(
            t,
            `status.matching.${matchingStatusKey}`,
            humanizeStatus(matchingStatusKey),
          ),
        );
        const tecdocLabel = safeTranslate(
          t,
          `status.tecdoc.${row.tecdoc_status}`,
          safeTranslate(t, "status.unknown", row.tecdoc_status || "-"),
        );
        const tooltipReasonLabel = safeTranslate(t, "products.statusTooltip.reason", "Reason");
        const tooltipTimeLabel = safeTranslate(t, "products.statusTooltip.time", "Time");
        const tooltipLookupLabel = safeTranslate(t, "products.statusTooltip.lookup", "Lookup");
        const tooltipMethodLabel = safeTranslate(t, "products.statusTooltip.method", "Method");
        const lookupValue = row.lookup_origin || "-";
        const methodValue = row.lookup_method || "-";

        return (
          <div className="grid gap-1">
            <BackofficeTooltip
              content={(
                <div className="grid gap-1">
                  <p><span className="font-semibold">{tooltipReasonLabel}:</span> {reasonText}</p>
                  <p><span className="font-semibold">{tooltipTimeLabel}:</span> {formatDateTime(evidenceTime)}</p>
                  {row.matching_status === "remote_found" ? (
                    <>
                      <p><span className="font-semibold">{tooltipLookupLabel}:</span> {lookupValue}</p>
                      <p><span className="font-semibold">{tooltipMethodLabel}:</span> {methodValue}</p>
                    </>
                  ) : null}
                </div>
              )}
              placement="top"
              align="start"
              wrapperClassName="inline-flex max-w-full"
              tooltipClassName="max-w-[420px] whitespace-normal break-words"
            >
              <BackofficeStatusChip tone={matching.tone} icon={matching.icon} className="max-w-full cursor-pointer">
                <span className="truncate">{matchingLabel}</span>
              </BackofficeStatusChip>
            </BackofficeTooltip>
            <BackofficeStatusChip tone={tecdoc.tone} icon={tecdoc.icon} className="max-w-full cursor-pointer">
              <span className="truncate">{tecdocLabel}</span>
            </BackofficeStatusChip>
          </div>
        );
      },
    },
    {
      key: "actions",
      label: t("products.columnsShort.actions"),
      className: "w-[104px]",
      render: (row) => (
        <div className="flex items-center gap-1">
          <BackofficeTooltip content={t("actions.details")} placement="top" align="center" wrapperClassName="inline-flex">
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
              style={surfaceStyle}
              onClick={() => onOpenDetails(row)}
              aria-label={t("actions.details")}
            >
              <SearchCode size={16} />
            </button>
          </BackofficeTooltip>
          <BackofficeTooltip content={t("actions.manualSearch")} placement="top" align="center" wrapperClassName="inline-flex">
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
              style={surfaceStyle}
              onClick={() => onSearchProduct(row)}
              aria-label={t("actions.manualSearch")}
            >
              <Search size={16} />
            </button>
          </BackofficeTooltip>
        </div>
      ),
    },
  ], [allPageSelected, onOpenDetails, onSearchProduct, onToggleSelectAllPage, onToggleSelected, selectedSet, t]);

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("states.emptyProducts")}>
      <BackofficeTable
        noHorizontalScroll
        rows={rows}
        columns={columns}
        emptyLabel={t("states.emptyProducts")}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("products.pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={surfaceStyle}
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t("common.prev")}
          </button>
          <span>{page} / {pagesCount}</span>
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={surfaceStyle}
            disabled={page >= pagesCount}
            onClick={() => onPageChange(Math.min(pagesCount, page + 1))}
          >
            {t("common.next")}
          </button>
        </div>
      </div>
    </AsyncState>
  );
}
