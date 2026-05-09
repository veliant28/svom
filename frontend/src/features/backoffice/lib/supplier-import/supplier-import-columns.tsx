import type { BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeSupplierPriceList } from "@/features/backoffice/types/suppliers.types";
import { Download, FileInput, RefreshCcw, Trash2 } from "lucide-react";

type Translator = (key: string, values?: Record<string, string | number>) => string;

const ALL_BRANDS_MARKERS = new Set([
  "all",
  "all brands",
  "все бренды",
  "усі бренди",
  "всі бренди",
]);

function getVisibleBrandsCount(item: BackofficeSupplierPriceList): number {
  if (item.supplier_code !== "utr") {
    return item.visible_brands.length;
  }

  const normalized = item.visible_brands
    .map((value) => String(value).trim())
    .filter(Boolean)
    .filter((value) => !ALL_BRANDS_MARKERS.has(value.toLowerCase()));
  return normalized.length;
}

export function createSupplierImportColumns({
  t,
  tokenReady,
  cooldownCanRun,
  onRowRequest,
  onRowDownload,
  onRowImport,
  onRowDelete,
}: {
  t: Translator;
  tokenReady: boolean;
  cooldownCanRun: boolean;
  onRowRequest: (item: BackofficeSupplierPriceList) => void;
  onRowDownload: (item: BackofficeSupplierPriceList) => void;
  onRowImport: (item: BackofficeSupplierPriceList) => void;
  onRowDelete: (item: BackofficeSupplierPriceList) => void;
}): Array<BackofficeColumn<BackofficeSupplierPriceList>> {
  const actionButtonClassName =
    "inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const actionTooltipClassName =
    "pointer-events-none absolute bottom-full left-1/2 z-[220] mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded-md border px-2 py-1 text-[11px] shadow-lg group-hover:block group-focus-within:block";

  return [
    {
      key: "file",
      label: t("priceLifecycle.table.columns.file"),
      className: "min-w-[230px]",
      render: (item) => (
        <div className="space-y-1">
          <p className="break-all font-semibold">{item.source_file_name || "-"}</p>
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
        const visibleBrandsCount = getVisibleBrandsCount(item);

        return (
          <div className="space-y-1.5 text-xs">
            <p>{t("priceLifecycle.table.paramFormat", { format: item.requested_format || "-" })}</p>
            {isGplRow ? (
              <div className="relative isolate flex flex-wrap items-center gap-3">
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
                {visibleBrandsCount ? (
                  <p>{t("priceLifecycle.table.paramBrands", { count: visibleBrandsCount })}</p>
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
      className: "min-w-[170px]",
      render: (item) => (
        <div className="flex flex-wrap gap-1.5">
          <span className="group relative inline-flex">
            <button
              type="button"
              aria-label={t("priceLifecycle.actions.request")}
              className={actionButtonClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              disabled={!tokenReady || !cooldownCanRun}
              onClick={() => onRowRequest(item)}
            >
              <RefreshCcw size={14} />
            </button>
            <span
              role="tooltip"
              className={actionTooltipClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
            >
              {t("priceLifecycle.actions.request")}
            </span>
          </span>
          <span className="group relative inline-flex">
            <button
              type="button"
              aria-label={t("priceLifecycle.actions.download")}
              className={actionButtonClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              disabled={!tokenReady || !item.download_available}
              onClick={() => onRowDownload(item)}
            >
              <Download size={14} />
            </button>
            <span
              role="tooltip"
              className={actionTooltipClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
            >
              {t("priceLifecycle.actions.download")}
            </span>
          </span>
          <span className="group relative inline-flex">
            <button
              type="button"
              aria-label={t("priceLifecycle.actions.import")}
              className={actionButtonClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              disabled={!tokenReady || !item.import_available}
              onClick={() => onRowImport(item)}
            >
              <FileInput size={14} />
            </button>
            <span
              role="tooltip"
              className={actionTooltipClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
            >
              {t("priceLifecycle.actions.import")}
            </span>
          </span>
          <span className="group relative inline-flex">
            <button
              type="button"
              aria-label={t("priceLifecycle.actions.delete")}
              className={actionButtonClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              disabled={!tokenReady}
              onClick={() => onRowDelete(item)}
            >
              <Trash2 size={14} />
            </button>
            <span
              role="tooltip"
              className={actionTooltipClassName}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
            >
              {t("priceLifecycle.actions.delete")}
            </span>
          </span>
        </div>
      ),
    },
  ];
}
