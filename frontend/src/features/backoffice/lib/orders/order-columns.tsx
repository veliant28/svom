import { Clock3, MinusCircle, ScanBarcode, ScanLine, TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";

import { OrderRowActions } from "@/features/backoffice/components/orders/order-row-actions";
import type { BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

import { formatOrderDate, formatOrderTotalWithCurrency } from "./order-formatters";

type Translator = (key: string, values?: Record<string, string | number>) => string;

const ATTENTION_WAYBILL_STATUS_CODES = new Set([
  "102", // refusal with return order
  "103", // refusal
  "104", // address changed
  "105", // storage stopped
  "111", // failed delivery attempt
  "112", // delivery date postponed by recipient
]);
const NP_STATUS_TEXT_CREATED_UK = "Відправник самостійно створив цю накладну, але ще не надав до відправки";
const WAYBILL_STATUS_CATALOG_CODES = new Set([
  "1",
  "2",
  "3",
  "4",
  "41",
  "5",
  "6",
  "7",
  "8",
  "9",
  "10",
  "11",
  "12",
  "101",
  "102",
  "103",
  "104",
  "105",
  "106",
  "111",
  "112",
]);

function resolveWaybillStatusView({
  t,
  statusCode,
  statusText,
  fallbackLabel,
}: {
  t: Translator;
  statusCode: string;
  statusText: string;
  fallbackLabel: string;
}): { shortLabel: string; tooltipLabel: string | null } {
  const normalizedCode = statusCode.trim();
  const normalizedText = statusText.trim();
  const localizedCode = WAYBILL_STATUS_CATALOG_CODES.has(normalizedCode)
    ? normalizedCode
    : normalizedText === NP_STATUS_TEXT_CREATED_UK
      ? "1"
      : "";

  if (localizedCode) {
    return {
      shortLabel: t(`orders.table.waybillStatusCatalog.${localizedCode}.short`),
      tooltipLabel: t(`orders.table.waybillStatusCatalog.${localizedCode}.full`),
    };
  }

  return {
    shortLabel: fallbackLabel,
    tooltipLabel: null,
  };
}

function compactPersonName(fullName: string): string {
  const normalized = fullName.trim();
  if (!normalized) {
    return "-";
  }

  const parts = normalized.split(/\s+/).filter(Boolean);
  if (parts.length <= 2) {
    return normalized;
  }

  return `${parts[0]} ${parts[1]}`.trim();
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

export function createOrderColumns({
  t,
  locale,
  selectedSet,
  allPageSelected,
  somePageSelected,
  deletingId,
  openingId,
  waybillLoadingId,
  supplierLoadingId,
  onToggleSelectAllPage,
  onToggleSelected,
  onOpen,
  onWaybill,
  onSupplierOrder,
  onDelete,
}: {
  t: Translator;
  locale: string;
  selectedSet: Set<string>;
  allPageSelected: boolean;
  somePageSelected: boolean;
  deletingId: string | null;
  openingId: string | null;
  waybillLoadingId: string | null;
  supplierLoadingId: string | null;
  onToggleSelectAllPage: () => void;
  onToggleSelected: (id: string) => void;
  onOpen: (item: BackofficeOrderOperational) => void;
  onWaybill: (item: BackofficeOrderOperational) => void;
  onSupplierOrder: (item: BackofficeOrderOperational) => void;
  onDelete: (item: BackofficeOrderOperational) => void;
}): Array<BackofficeColumn<BackofficeOrderOperational>> {
  return [
    {
      key: "select",
      label: (
        <SelectAllPageCheckbox
          checked={allPageSelected}
          indeterminate={!allPageSelected && somePageSelected}
          ariaLabel={t("orders.tooltips.selectAll")}
          onChange={onToggleSelectAllPage}
        />
      ),
      className: "w-[2%]",
      render: (item) => (
        <input
          type="checkbox"
          checked={selectedSet.has(item.id)}
          aria-label={t("orders.tooltips.selectOne", { orderNumber: item.order_number })}
          onChange={() => onToggleSelected(item.id)}
        />
      ),
    },
    {
      key: "order",
      label: t("orders.table.columns.order"),
      className: "w-[17%]",
      render: (item) => (
        <div className="min-w-0">
          <p className="break-words font-semibold leading-tight">{item.order_number}</p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>
            {t("orders.table.itemsCount", { count: item.items_count })}
          </p>
        </div>
      ),
    },
    {
      key: "client",
      label: t("orders.table.columns.client"),
      className: "w-[13%]",
      render: (item) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{compactPersonName(item.contact_full_name || "")}</p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>
            {item.contact_phone || "-"}
          </p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>
            {item.contact_email || item.user_email || "-"}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      label: t("orders.table.columns.status"),
      className: "w-[13%]",
      render: (item) => <StatusChip status={item.status} />,
    },
    {
      key: "totals",
      label: t("orders.table.columns.total"),
      className: "w-[10%]",
      render: (item) => (
        <div className="min-w-0">
          <p className="truncate font-semibold tabular-nums">{formatOrderTotalWithCurrency(item.total, item.currency, locale)}</p>
        </div>
      ),
    },
    {
      key: "created",
      label: t("orders.table.columns.created"),
      className: "w-[7%]",
      render: (item) => (
        <span className="text-xs" style={{ color: "var(--muted)" }}>
          {formatOrderDate(item.placed_at)}
        </span>
      ),
    },
    {
      key: "waybill",
      label: t("orders.table.columns.waybill"),
      className: "w-[13%]",
      render: (item) => {
        if (!item.nova_poshta_waybill_exists || !item.nova_poshta_waybill_number) {
          return (
            <BackofficeStatusChip tone="orange" icon={ScanLine}>
              {t("orders.table.waybillEmpty")}
            </BackofficeStatusChip>
          );
        }

        return (
          <BackofficeTooltip
            content={item.nova_poshta_waybill_number}
            placement="top"
            align="center"
            wrapperClassName="inline-flex"
            tooltipClassName="whitespace-nowrap"
          >
            <BackofficeStatusChip tone="success" icon={ScanBarcode}>
              {item.nova_poshta_waybill_number}
            </BackofficeStatusChip>
          </BackofficeTooltip>
        );
      },
    },
    {
      key: "waybill_status",
      label: t("orders.table.columns.waybillStatus"),
      className: "w-[10%]",
      render: (item) => {
        if (!item.nova_poshta_waybill_exists) {
          return (
            <BackofficeStatusChip tone="gray" icon={MinusCircle}>
              {t("orders.table.waybillStatusEmpty")}
            </BackofficeStatusChip>
          );
        }

        const hasError = item.nova_poshta_waybill_has_error;
        const statusCode = String(item.nova_poshta_waybill_status_code || "").trim();
        const hasAttention = ATTENTION_WAYBILL_STATUS_CODES.has(statusCode);
        const rawStatusText = String(item.nova_poshta_waybill_status_text || "").trim();
        const fallbackLabel = rawStatusText || item.nova_poshta_waybill_status_code || t("orders.table.waybillStatusUnknown");
        const statusView = resolveWaybillStatusView({
          t,
          statusCode,
          statusText: rawStatusText,
          fallbackLabel,
        });
        const chip = (
          <BackofficeStatusChip
            tone={hasError ? "error" : hasAttention ? "warning" : "blue"}
            icon={hasError || hasAttention ? TriangleAlert : Clock3}
          >
            {statusView.shortLabel}
          </BackofficeStatusChip>
        );
        if (!statusView.tooltipLabel) {
          return chip;
        }
        return (
          <BackofficeTooltip
            content={statusView.tooltipLabel}
            placement="top"
            align="center"
            wrapperClassName="inline-flex"
          >
            {chip}
          </BackofficeTooltip>
        );
      },
    },
    {
      key: "actions",
      label: t("orders.table.columns.actions"),
      className: "w-[15%] min-w-[156px]",
      render: (item) => (
        <OrderRowActions
          hasWaybill={Boolean(item.nova_poshta_waybill_exists && item.nova_poshta_waybill_number)}
          deleting={deletingId === item.id}
          opening={openingId === item.id}
          processingWaybill={waybillLoadingId === item.id}
          processingSupplier={supplierLoadingId === item.id}
          onOpen={() => onOpen(item)}
          onWaybill={() => onWaybill(item)}
          onSupplierOrder={() => onSupplierOrder(item)}
          onDelete={() => onDelete(item)}
          t={t}
        />
      ),
    },
  ];
}
