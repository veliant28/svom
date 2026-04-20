"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  cancelBackofficeOrder,
  confirmBackofficeOrder,
  getBackofficeOrderDetail,
  getBackofficeOrderItemSupplierRecommendation,
  markBackofficeOrderAwaitingProcurement,
  markBackofficeOrderReadyToShip,
  overrideBackofficeOrderItemSupplier,
  refreshBackofficeOrderPayment,
  reserveBackofficeOrder,
} from "@/features/backoffice/api/backoffice-api";
import { OrderPaymentSection } from "@/features/backoffice/components/orders/payment/order-payment-section";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeOrderOperational, BackofficeProcurementRecommendation } from "@/features/backoffice/types/backoffice";
import { Link } from "@/i18n/navigation";

export function OrderDetailPage({ orderId }: { orderId: string }) {
  const t = useTranslations("backoffice.common");
  const [itemRecommendations, setItemRecommendations] = useState<Record<string, BackofficeProcurementRecommendation>>({});
  const [cancelReason, setCancelReason] = useState("supplier_shortage");
  const [paymentRefreshing, setPaymentRefreshing] = useState(false);

  const queryFn = useCallback((token: string) => getBackofficeOrderDetail(token, orderId), [orderId]);
  const { token, data, isLoading, error, refetch } = useBackofficeQuery<BackofficeOrderOperational>(queryFn, [orderId]);

  const items = data?.items ?? [];
  const recommendedByItem = useMemo(() => itemRecommendations, [itemRecommendations]);

  async function runConfirm() {
    if (!token || !data) {
      return;
    }
    await confirmBackofficeOrder(token, { order_id: data.id });
    await refetch();
  }

  async function runAwaitingProcurement() {
    if (!token || !data) {
      return;
    }
    await markBackofficeOrderAwaitingProcurement(token, { order_id: data.id });
    await refetch();
  }

  async function runReserve() {
    if (!token || !data) {
      return;
    }
    await reserveBackofficeOrder(token, { order_id: data.id });
    await refetch();
  }

  async function runReadyToShip() {
    if (!token || !data) {
      return;
    }
    await markBackofficeOrderReadyToShip(token, { order_id: data.id });
    await refetch();
  }

  async function runCancel() {
    if (!token || !data) {
      return;
    }
    await cancelBackofficeOrder(token, {
      order_id: data.id,
      reason_code: cancelReason,
    });
    await refetch();
  }

  async function runRecommendation(itemId: string) {
    if (!token) {
      return;
    }
    const recommendation = await getBackofficeOrderItemSupplierRecommendation(token, itemId);
    setItemRecommendations((prev) => ({
      ...prev,
      [itemId]: recommendation,
    }));
  }

  async function applyRecommendedSupplier(itemId: string) {
    if (!token) {
      return;
    }
    const recommendation = recommendedByItem[itemId];
    const offerId = recommendation?.recommended_offer.offer_id;
    if (!offerId) {
      return;
    }
    await overrideBackofficeOrderItemSupplier(token, itemId, { supplier_offer_id: offerId });
    await refetch();
  }

  async function refreshPaymentStatus() {
    if (!token || !data || paymentRefreshing) {
      return;
    }
    setPaymentRefreshing(true);
    try {
      await refreshBackofficeOrderPayment(token, data.id);
      await refetch();
    } finally {
      setPaymentRefreshing(false);
    }
  }

  return (
    <section>
      <PageHeader
        title={data ? t("orderDetail.titleWithNumber", { orderNumber: data.order_number }) : t("orderDetail.title")}
        description={t("orderDetail.subtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/backoffice/orders"
              className="inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              {t("orderDetail.actions.backToOrders")}
            </Link>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runConfirm();
              }}
            >
              {t("orderDetail.actions.confirm")}
            </button>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runAwaitingProcurement();
              }}
            >
              {t("orderDetail.actions.awaiting")}
            </button>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runReserve();
              }}
            >
              {t("orderDetail.actions.reserve")}
            </button>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runReadyToShip();
              }}
            >
              {t("orderDetail.actions.readyToShip")}
            </button>
            <select
              value={cancelReason}
              onChange={(event) => setCancelReason(event.target.value)}
              className="h-9 rounded-md border px-3 text-xs"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <option value="customer_request">{t("orderDetail.cancelReasons.customer_request")}</option>
              <option value="payment_failed">{t("orderDetail.cancelReasons.payment_failed")}</option>
              <option value="supplier_shortage">{t("orderDetail.cancelReasons.supplier_shortage")}</option>
              <option value="unavailable">{t("orderDetail.cancelReasons.unavailable")}</option>
              <option value="operator_decision">{t("orderDetail.cancelReasons.operator_decision")}</option>
              <option value="other">{t("orderDetail.cancelReasons.other")}</option>
            </select>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void runCancel();
              }}
            >
              {t("orderDetail.actions.cancel")}
            </button>
          </div>
        }
      />

      <AsyncState isLoading={isLoading} error={error} empty={!data} emptyLabel={t("orderDetail.states.notFound")}>
        {data ? (
          <div className="grid gap-4">
            <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <div className="grid gap-3 md:grid-cols-3">
                <div>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {t("orderDetail.summary.status")}
                  </p>
                  <StatusChip status={data.status} />
                </div>
                <div>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {t("orderDetail.summary.customer")}
                  </p>
                  <p className="text-sm font-semibold">{data.contact_full_name}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {data.contact_phone} · {data.contact_email}
                  </p>
                </div>
                <div>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {t("orderDetail.summary.totals")}
                  </p>
                  <p className="text-sm font-semibold">
                    {data.total} {data.currency}
                  </p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {t("orderDetail.summary.itemsIssues", { items: data.items_count, issues: data.issues_count })}
                  </p>
                </div>
              </div>
            </div>

            <OrderPaymentSection
              payment={data.payment}
              t={t}
              onRefresh={() => {
                void refreshPaymentStatus();
              }}
              isRefreshing={paymentRefreshing}
            />

            <BackofficeTable
              emptyLabel={t("orderDetail.states.emptyItems")}
              rows={items}
              columns={[
                {
                  key: "product",
                  label: t("orderDetail.table.columns.product"),
                  render: (item) => (
                    <div>
                      <p className="font-semibold">{item.product_name}</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>
                        {item.product_sku}
                      </p>
                    </div>
                  ),
                },
                {
                  key: "qty",
                  label: t("orderDetail.table.columns.qty"),
                  render: (item) => item.quantity,
                },
                {
                  key: "availability",
                  label: t("orderDetail.table.columns.availability"),
                  render: (item) => (
                    <div>
                      <p className="text-xs font-semibold">{item.snapshot_availability_label}</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>
                        {t("orderDetail.table.eta", { days: item.snapshot_estimated_delivery_days ?? "-" })}
                      </p>
                    </div>
                  ),
                },
                {
                  key: "suppliers",
                  label: t("orderDetail.table.columns.supplier"),
                  render: (item) => {
                    const recommendation = recommendedByItem[item.id];
                    return (
                      <div>
                        <p className="text-xs">{t("orderDetail.table.recommended", { value: item.recommended_supplier_name || "-" })}</p>
                        <p className="text-xs">{t("orderDetail.table.selected", { value: item.selected_supplier_name || "-" })}</p>
                        {recommendation ? (
                          <p className="text-xs" style={{ color: "var(--muted)" }}>
                            {t("orderDetail.table.suggestedNow", { value: recommendation.recommended_offer.supplier_name || "-" })}
                          </p>
                        ) : null}
                      </div>
                    );
                  },
                },
                {
                  key: "procurement",
                  label: t("orderDetail.table.columns.procurement"),
                  render: (item) => <StatusChip status={item.procurement_status} />,
                },
                {
                  key: "actions",
                  label: t("orderDetail.table.columns.actions"),
                  render: (item) => (
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="h-8 rounded-md border px-2 text-xs"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        onClick={() => {
                          void runRecommendation(item.id);
                        }}
                      >
                        {t("orderDetail.actions.recommendSupplier")}
                      </button>
                      <button
                        type="button"
                        className="h-8 rounded-md border px-2 text-xs"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        onClick={() => {
                          void applyRecommendedSupplier(item.id);
                        }}
                      >
                        {t("orderDetail.actions.setRecommendedSupplier")}
                      </button>
                    </div>
                  ),
                },
              ]}
            />
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
