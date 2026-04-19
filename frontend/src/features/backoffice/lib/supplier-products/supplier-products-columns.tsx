import { BadgeDollarSign } from "lucide-react";

import { SupplierProductsRowActions } from "@/features/backoffice/components/supplier-products/supplier-products-row-actions";
import type { BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import { priceDigitsOnly } from "@/features/backoffice/lib/supplier-products/supplier-products-formatters";
import { extractPriceLevels } from "@/features/backoffice/lib/supplier-products/supplier-products-price-utils";
import { compactWarehouseName, extractWarehouses, formatWarehouseQty, resolveWarehouseTone } from "@/features/backoffice/lib/supplier-products/supplier-products-warehouse-utils";
import type { BackofficeRawOffer } from "@/features/backoffice/types/imports.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function createSupplierProductsColumns({
  t,
  tUtr,
  tGpl,
  onOpenCategoryMapping,
  isCategoryMappingOpen,
  selectedRawOfferId,
}: {
  t: Translator;
  tUtr: Translator;
  tGpl: Translator;
  onOpenCategoryMapping: (rawOfferId: string) => void;
  isCategoryMappingOpen: boolean;
  selectedRawOfferId: string | null;
}): Array<BackofficeColumn<BackofficeRawOffer>> {
  return [
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
        <SupplierProductsRowActions
          status={item.category_mapping_status || "unmapped"}
          mappedCategoryPath={item.mapped_category_path}
          expanded={isCategoryMappingOpen && selectedRawOfferId === item.id}
          onOpen={() => onOpenCategoryMapping(item.id)}
          t={t}
        />
      ),
    },
  ];
}
