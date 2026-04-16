"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  bulkConfirmBackofficeOrders,
  bulkMarkAwaitingProcurementBackofficeOrders,
  confirmBackofficeOrder,
  getBackofficeOrders,
  markBackofficeOrderAwaitingProcurement,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/backoffice";
import { Link } from "@/i18n/navigation";

export function OrdersPage() {
  const t = useTranslations("backoffice.common");
  const tStatus = useTranslations("backoffice.common");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeOrders(token, {
        q,
        status,
      }),
    [q, status],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeOrderOperational[] }>(queryFn, [q, status]);
  const rows = data?.results ?? [];

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  function toggleSelected(orderId: string) {
    setSelectedIds((prev) => {
      if (prev.includes(orderId)) {
        return prev.filter((id) => id !== orderId);
      }
      return [...prev, orderId];
    });
  }

  async function runBulkConfirm() {
    if (!token || selectedIds.length === 0) {
      return;
    }
    await bulkConfirmBackofficeOrders(token, { order_ids: selectedIds });
    setSelectedIds([]);
    await refetch();
  }

  async function runBulkAwaiting() {
    if (!token || selectedIds.length === 0) {
      return;
    }
    await bulkMarkAwaitingProcurementBackofficeOrders(token, { order_ids: selectedIds });
    setSelectedIds([]);
    await refetch();
  }

  async function runConfirm(orderId: string) {
    if (!token) {
      return;
    }
    await confirmBackofficeOrder(token, { order_id: orderId });
    await refetch();
  }

  async function runAwaiting(orderId: string) {
    if (!token) {
      return;
    }
    await markBackofficeOrderAwaitingProcurement(token, { order_id: orderId });
    await refetch();
  }

  return (
    <section>
      <PageHeader
        title={t("orders.title")}
        description={t("orders.subtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void refetch();
              }}
            >
              {t("orders.actions.refresh")}
            </button>
            <button
              type="button"
              disabled={!selectedIds.length}
              className="h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-50"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runBulkConfirm();
              }}
            >
              {t("orders.actions.bulkConfirm")}
            </button>
            <button
              type="button"
              disabled={!selectedIds.length}
              className="h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-50"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runBulkAwaiting();
              }}
            >
              {t("orders.actions.bulkAwaiting")}
            </button>
          </div>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("orders.filters.search")}
          className="h-9 min-w-[220px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("orders.filters.allStatuses")}</option>
          <option value="new">{tStatus("statuses.new")}</option>
          <option value="confirmed">{tStatus("statuses.confirmed")}</option>
          <option value="awaiting_procurement">{tStatus("statuses.awaiting_procurement")}</option>
          <option value="reserved">{tStatus("statuses.reserved")}</option>
          <option value="partially_reserved">{tStatus("statuses.partially_reserved")}</option>
          <option value="ready_to_ship">{tStatus("statuses.ready_to_ship")}</option>
          <option value="shipped">{tStatus("statuses.shipped")}</option>
          <option value="completed">{tStatus("statuses.completed")}</option>
          <option value="cancelled">{tStatus("statuses.cancelled")}</option>
        </select>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("orders.states.empty")}>
        <BackofficeTable
          emptyLabel={t("orders.states.empty")}
          rows={rows}
          columns={[
            {
              key: "select",
              label: t("orders.table.columns.select"),
              render: (item) => (
                <input
                  type="checkbox"
                  checked={selectedSet.has(item.id)}
                  onChange={() => toggleSelected(item.id)}
                />
              ),
            },
            {
              key: "order",
              label: t("orders.table.columns.order"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{item.order_number}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {item.contact_full_name}
                  </p>
                </div>
              ),
            },
            {
              key: "status",
              label: t("orders.table.columns.status"),
              render: (item) => <StatusChip status={item.status} />,
            },
            {
              key: "issues",
              label: t("orders.table.columns.issues"),
              render: (item) => item.issues_count,
            },
            {
              key: "totals",
              label: t("orders.table.columns.total"),
              render: (item) => `${item.total} ${item.currency}`,
            },
            {
              key: "actions",
              label: t("orders.table.columns.actions"),
              render: (item) => (
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={`/backoffice/orders/${item.id}`}
                    className="inline-flex h-8 items-center rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  >
                    {t("orders.actions.open")}
                  </Link>
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void runConfirm(item.id);
                    }}
                  >
                    {t("orders.actions.confirm")}
                  </button>
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void runAwaiting(item.id);
                    }}
                  >
                    {t("orders.actions.awaiting")}
                  </button>
                </div>
              ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
