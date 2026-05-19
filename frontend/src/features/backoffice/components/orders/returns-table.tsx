"use client";

import { Eye, ScanBarcode, ScanLine } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { BackofficeTable, type BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { ReturnStatusChip } from "@/features/backoffice/components/widgets/return-status-chip";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeReturnOperational } from "@/features/backoffice/types/returns.types";
import { formatFooterPhoneDisplay } from "@/shared/lib/footer-phone";

type Translator = (key: string, values?: Record<string, string | number>) => string;

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
    <input
      ref={inputRef}
      type="checkbox"
      checked={checked}
      aria-label={ariaLabel}
      onChange={onChange}
    />
  );
}

export function ReturnsTable({
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
  onToggleSelectAllPage,
  onToggleSelected,
  onOpen,
  onPageChange,
}: {
  t: Translator;
  rows: BackofficeReturnOperational[];
  isLoading: boolean;
  error: string | null;
  page: number;
  pagesCount: number;
  totalCount: number;
  selectedSet: Set<string>;
  allPageSelected: boolean;
  somePageSelected: boolean;
  onToggleSelectAllPage: () => void;
  onToggleSelected: (id: string) => void;
  onOpen: (item: BackofficeReturnOperational) => void;
  onPageChange: (next: number) => void;
}) {
  const columns = useMemo<Array<BackofficeColumn<BackofficeReturnOperational>>>(() => [
    {
      key: "select",
      label: (
        <SelectAllPageCheckbox
          checked={allPageSelected}
          indeterminate={!allPageSelected && somePageSelected}
          ariaLabel={t("returns.tooltips.selectAll")}
          onChange={onToggleSelectAllPage}
        />
      ),
      className: "w-[2%]",
      render: (item) => (
        <input
          type="checkbox"
          checked={selectedSet.has(item.id)}
          aria-label={t("returns.tooltips.selectOne", { returnNumber: item.return_number })}
          onChange={() => onToggleSelected(item.id)}
        />
      ),
    },
    {
      key: "return_order",
      label: t("returns.table.columns.returnOrder"),
      className: "w-[20%]",
      render: (item) => (
        <div className="min-w-0">
          <p className="truncate font-semibold">{item.return_number}</p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{item.order_number}</p>
        </div>
      ),
    },
    {
      key: "customer",
      label: t("returns.table.columns.customer"),
      className: "w-[15%]",
      render: (item) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{item.customer_name || "-"}</p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{formatFooterPhoneDisplay(item.customer_phone || "") || "-"}</p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{item.customer_email || "-"}</p>
        </div>
      ),
    },
    {
      key: "status",
      label: t("returns.table.columns.status"),
      className: "w-[12%]",
      render: (item) => <ReturnStatusChip status={item.status} />,
    },
    {
      key: "amount",
      label: t("returns.labels.total"),
      className: "w-[10%]",
      render: (item) => <p className="font-semibold tabular-nums">{item.refund_amount} UAH</p>,
    },
    {
      key: "date",
      label: t("returns.table.columns.date"),
      className: "w-[12%]",
      render: (item) => (
        <div className="text-xs" style={{ color: "var(--muted)" }}>
          <p>{formatBackofficeDate(item.created_at)}</p>
          <p>{item.return_day_label || "-"}</p>
        </div>
      ),
    },
    {
      key: "tracking",
      label: t("returns.table.columns.tracking"),
      className: "w-[15%]",
      render: (item) => (
        item.tracking_number
          ? <BackofficeStatusChip tone="success" icon={ScanBarcode}>{item.tracking_number}</BackofficeStatusChip>
          : <BackofficeStatusChip tone="orange" icon={ScanLine}>{t("returns.labels.noTtn")}</BackofficeStatusChip>
      ),
    },
    {
      key: "actions",
      label: t("returns.table.columns.actions"),
      className: "w-[8%]",
      render: (item) => (
        <ActionIconButton label={t("returns.actions.open")} icon={Eye} onClick={() => onOpen(item)} />
      ),
    },
  ], [allPageSelected, onOpen, onToggleSelectAllPage, onToggleSelected, selectedSet, somePageSelected, t]);

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("returns.states.empty")}>
      <BackofficeTable
        noHorizontalScroll
        rows={rows}
        columns={columns}
        emptyLabel={t("returns.states.empty")}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("returns.pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            {t("returns.pagination.prev")}
          </button>
          <span>{t("returns.pagination.page", { current: page, total: pagesCount })}</span>
          <button
            type="button"
            className="h-8 rounded-md border px-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={page >= pagesCount}
            onClick={() => onPageChange(Math.min(pagesCount, page + 1))}
          >
            {t("returns.pagination.next")}
          </button>
        </div>
      </div>
    </AsyncState>
  );
}
