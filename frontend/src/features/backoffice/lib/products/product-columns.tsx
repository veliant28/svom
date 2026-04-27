import { useEffect, useRef, type ReactNode } from "react";
import { BadgeDollarSign, CheckCircle2, Flame, Sparkles, Star, XCircle, type LucideIcon } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { ProductRowActions } from "@/features/backoffice/components/products/product-row-actions";
import type { BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";

import { buildProductPriceMeta } from "./price-utils";
import { extractWarehouseSegments, formatWarehouseLabel, formatWarehouseQty, resolveWarehouseTone } from "./warehouse-utils";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function StatusIconChip({
  label,
  tooltipContent,
  tone,
  icon,
}: {
  label: string;
  tooltipContent?: ReactNode;
  tone: BackofficeStatusChipTone;
  icon: LucideIcon;
}) {
  return (
    <BackofficeTooltip
      content={tooltipContent || label}
      placement="top"
      align="center"
      wrapperClassName="inline-flex"
      tooltipClassName={tooltipContent ? "min-w-[190px]" : "whitespace-nowrap"}
    >
      <BackofficeStatusChip
        tone={tone}
        icon={icon}
        className="cursor-help justify-center gap-0 px-1.5 [&>span:last-child]:hidden"
      >
        <span className="sr-only">{label}</span>
      </BackofficeStatusChip>
    </BackofficeTooltip>
  );
}

function SelectAllPageCheckbox({
  checked,
  indeterminate,
  ariaLabel,
  onChange,
}: {
  checked: boolean;
  indeterminate: boolean;
  ariaLabel: string;
  onChange: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!inputRef.current) {
      return;
    }
    inputRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <BackofficeTooltip
      content={ariaLabel}
      placement="bottom"
      align="center"
      wrapperClassName="inline-flex items-center justify-center"
      tooltipClassName="whitespace-nowrap normal-case"
    >
      <input
        ref={inputRef}
        type="checkbox"
        checked={checked}
        aria-label={ariaLabel}
        onChange={onChange}
      />
    </BackofficeTooltip>
  );
}

export function createProductColumns({
  t,
  tUtr,
  tGpl,
  locale,
  selectedSet,
  allPageSelected,
  somePageSelected,
  onToggleSelectAllPage,
  onToggleSelected,
  onOpenEdit,
  onRequestDelete,
  deletingId,
}: {
  t: Translator;
  tUtr: Translator;
  tGpl: Translator;
  locale: string;
  selectedSet: Set<string>;
  allPageSelected: boolean;
  somePageSelected: boolean;
  onToggleSelectAllPage: () => void;
  onToggleSelected: (id: string) => void;
  onOpenEdit: (item: BackofficeCatalogProduct) => void;
  onRequestDelete: (item: BackofficeCatalogProduct) => void;
  deletingId: string | null;
}): Array<BackofficeColumn<BackofficeCatalogProduct>> {
  return [
    {
      key: "select",
      label: (
        <span className="flex items-center justify-center">
          <SelectAllPageCheckbox
            checked={allPageSelected}
            indeterminate={!allPageSelected && somePageSelected}
            ariaLabel={allPageSelected ? t("products.actions.unselectPage") : t("products.actions.selectPage")}
            onChange={onToggleSelectAllPage}
          />
        </span>
      ),
      className: "w-[5%] text-center",
      render: (item) => (
        <div className="flex items-center justify-center">
          <input
            type="checkbox"
            checked={selectedSet.has(item.id)}
            aria-label={`${t("products.table.columns.select")}: ${item.name}`}
            onChange={() => onToggleSelected(item.id)}
          />
        </div>
      ),
    },
    {
      key: "brand",
      label: t("products.table.columns.brand"),
      className: "w-[8%]",
      render: (item) => item.brand_name || "-",
    },
    {
      key: "product",
      label: t("products.table.columns.product"),
      className: "w-[24%]",
      render: (item) => {
        const supplierSku = (item.supplier_sku || item.sku || "").trim() || "-";
        return (
          <div className="min-w-0">
            <BackofficeTooltip
              content={item.name}
              placement="top"
              align="start"
              wrapperClassName="inline-flex max-w-full"
              tooltipClassName="max-w-[320px]"
            >
              <span tabIndex={0} className="block truncate cursor-help font-semibold">
                {item.name}
              </span>
            </BackofficeTooltip>
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              {t("products.fields.sku")}: {supplierSku}
            </p>
          </div>
        );
      },
    },
    {
      key: "price",
      label: t("products.table.columns.price"),
      className: "w-[14%]",
      render: (item) => {
        if (!item.final_price && !item.supplier_price && !(item.supplier_price_levels ?? []).length) {
          return <span>-</span>;
        }

        const priceMeta = buildProductPriceMeta({ item, locale, t });

        return (
          <BackofficeTooltip
            content={(
              <span className="grid gap-1">
                <span>
                  <span style={{ color: "var(--muted)" }}>{t("products.tooltips.priceWithMarkup")}:</span>{" "}
                  {priceMeta.displayPrice}
                </span>
                <span>
                  <span style={{ color: "var(--muted)" }}>{t("products.tooltips.supplierPrice")}:</span>{" "}
                  {priceMeta.supplierPrice}
                </span>
                {priceMeta.supplierPriceLevels.length ? (
                  <span className="grid gap-0.5 border-t pt-1" style={{ borderColor: "var(--border)" }}>
                    {priceMeta.supplierPriceLevels.map((level) => (
                      <span key={`${item.id}-supplier-price-level-${level.key}`}>
                        <span style={{ color: level.is_primary ? "var(--text)" : "var(--muted)" }}>
                          {level.label}{level.is_primary ? " *" : ""}:
                        </span>{" "}
                        {level.formattedValue}
                      </span>
                    ))}
                  </span>
                ) : null}
                <span>
                  <span style={{ color: "var(--muted)" }}>{t("products.tooltips.appliedMarkup")}:</span>{" "}
                  {priceMeta.appliedMarkup}
                </span>
                {priceMeta.hasPolicy ? (
                  <span>
                    <span style={{ color: "var(--muted)" }}>{t("products.tooltips.policy")}:</span>{" "}
                    {priceMeta.appliedPolicyLabel}
                  </span>
                ) : null}
                <span>
                  <span style={{ color: "var(--muted)" }}>{t("products.tooltips.updatedAt")}:</span>{" "}
                  {priceMeta.priceUpdatedAtLabel}
                </span>
              </span>
            )}
            placement="top"
            align="start"
            wrapperClassName="inline-flex max-w-full"
            tooltipClassName="min-w-[220px]"
          >
            <BackofficeStatusChip
              tone="blue"
              icon={BadgeDollarSign}
              className="w-full max-w-full min-w-0 cursor-help justify-start overflow-hidden"
            >
              <span className="block min-w-0 truncate tabular-nums">{priceMeta.badgeLabel}</span>
            </BackofficeStatusChip>
          </BackofficeTooltip>
        );
      },
    },
    {
      key: "status",
      label: t("products.table.columns.status"),
      className: "w-[8%]",
      render: (item) => {
        const statusLabel = item.is_active ? t("statuses.active") : t("statuses.inactive");
        const supplierOfferSeenAtLabel = item.supplier_offer_seen_at
          ? formatBackofficeDate(item.supplier_offer_seen_at)
          : t("products.tooltips.notSet");

        return (
          <div className="flex flex-wrap gap-1">
            <StatusIconChip
              label={statusLabel}
              tooltipContent={(
                <span className="grid gap-1">
                  <span>
                    <span style={{ color: "var(--muted)" }}>{t("products.table.columns.status")}:</span>{" "}
                    {statusLabel}
                  </span>
                  <span>
                    <span style={{ color: "var(--muted)" }}>{t("products.tooltips.importedFromPriceAt")}:</span>{" "}
                    {supplierOfferSeenAtLabel}
                  </span>
                </span>
              )}
              tone={item.is_active ? "success" : "gray"}
              icon={item.is_active ? CheckCircle2 : XCircle}
            />
            {item.is_featured ? <StatusIconChip label={t("products.flags.featured")} tone="info" icon={Star} /> : null}
            {item.is_new ? <StatusIconChip label={t("products.flags.new")} tone="orange" icon={Sparkles} /> : null}
            {item.is_bestseller ? <StatusIconChip label={t("products.flags.bestseller")} tone="blue" icon={Flame} /> : null}
          </div>
        );
      },
    },
    {
      key: "warehouses",
      label: t("products.table.columns.warehouses"),
      className: "w-[32%]",
      render: (item) => {
        const warehouses = extractWarehouseSegments(item);

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
                  warehouse.source_code === "utr"
                    ? tUtr("label")
                    : warehouse.source_code === "gpl"
                      ? tGpl("label")
                      : warehouse.source_code.toUpperCase();
                const warehouseLabel = formatWarehouseLabel(warehouse.key);
                const qtyLabel = formatWarehouseQty(warehouse.qty);

                return (
                  <BackofficeTooltip
                    key={`${item.id}-warehouse-${warehouse.key}`}
                    content={(
                      <span className="grid gap-1">
                        <span className="font-semibold">{supplierLabel}</span>
                        <span>
                          <span style={{ color: "var(--muted)" }}>{t("products.table.columns.warehouses")}:</span>{" "}
                          {warehouseLabel}
                        </span>
                        <span>
                          <span style={{ color: "var(--muted)" }}>{t("products.table.columns.stock")}:</span>{" "}
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
                      aria-label={`${warehouseLabel}, ${t("products.table.columns.stock")}: ${warehouse.value}`}
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
      key: "actions",
      label: t("products.table.columns.actions"),
      className: "w-[8%] min-w-[96px] whitespace-nowrap",
      render: (item) => (
        <ProductRowActions
          deleting={deletingId === item.id}
          onEdit={() => onOpenEdit(item)}
          onDelete={() => onRequestDelete(item)}
          t={t}
        />
      ),
    },
  ];
}
