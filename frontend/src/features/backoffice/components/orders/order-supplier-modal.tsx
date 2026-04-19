import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import type { BackofficeOrderOperational, BackofficeOrderSupplierPayloadPreview } from "@/features/backoffice/types/orders.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrderSupplierModal({
  isOpen,
  order,
  preview,
  isLoading,
  isSubmitting,
  isCancelling,
  onRefresh,
  onSubmit,
  onCancelSupplierOrder,
  onClose,
  t,
}: {
  isOpen: boolean;
  order: BackofficeOrderOperational | null;
  preview: BackofficeOrderSupplierPayloadPreview | null;
  isLoading: boolean;
  isSubmitting: boolean;
  isCancelling: boolean;
  onRefresh: () => void;
  onSubmit: () => void;
  onCancelSupplierOrder: () => void;
  onClose: () => void;
  t: Translator;
}) {
  if (!isOpen) {
    return null;
  }

  const items = preview?.items ?? [];
  const payloadProducts = preview?.products ?? [];
  const canSubmit = Boolean(preview?.can_submit) && payloadProducts.length > 0;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("orders.actions.closeModal")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      <div className="relative z-10 flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <header className="border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <h2 className="text-base font-semibold">{t("orders.modals.supplier.title")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            {order ? t("orders.modals.supplier.subtitleWithNumber", { number: order.order_number }) : t("orders.modals.supplier.subtitle")}
          </p>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          <section className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="text-sm font-semibold">{t("orders.modals.supplier.explainTitle")}</p>
            <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{t("orders.modals.supplier.explainBody")}</p>
          </section>

          <section className="mt-3 rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <div className="flex items-center justify-between border-b px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="text-sm font-semibold">{t("orders.modals.supplier.itemsTitle")}</p>
              <button
                type="button"
                className="h-8 rounded-md border px-2 text-xs"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                disabled={isLoading || isSubmitting || isCancelling}
                onClick={onRefresh}
              >
                {isLoading ? t("loading") : t("orders.actions.refresh")}
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide">{t("orders.modals.supplier.columns.article")}</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide">{t("orders.modals.supplier.columns.name")}</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide">{t("orders.modals.supplier.columns.qty")}</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide">{t("orders.modals.supplier.columns.price")}</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide">{t("orders.modals.supplier.columns.total")}</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide">{t("orders.modals.supplier.columns.mapping")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length ? items.map((item) => (
                    <tr key={item.item_id} className="border-t" style={{ borderColor: "var(--border)" }}>
                      <td className="px-3 py-2 align-top font-mono text-xs">{item.product_sku || "-"}</td>
                      <td className="px-3 py-2 align-top">
                        <p className="font-medium">{item.product_name}</p>
                      </td>
                      <td className="px-3 py-2 align-top tabular-nums">{item.quantity}</td>
                      <td className="px-3 py-2 align-top tabular-nums">{item.unit_price} {order?.currency ?? ""}</td>
                      <td className="px-3 py-2 align-top tabular-nums">{item.line_total} {order?.currency ?? ""}</td>
                      <td className="px-3 py-2 align-top text-xs">
                        {item.gpl_product_id ? (
                          <BackofficeTooltip
                            content={t("orders.modals.supplier.mapping.tooltip", { id: item.gpl_product_id })}
                            placement="top"
                            tooltipClassName="whitespace-nowrap"
                          >
                            <span className="inline-flex rounded-md border px-2 py-0.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                              {t("orders.modals.supplier.mapping.ok")}
                            </span>
                          </BackofficeTooltip>
                        ) : (
                          <span className="inline-flex rounded-md border border-red-500/55 bg-red-500/10 px-2 py-0.5 text-red-700 dark:border-red-300/70 dark:bg-red-500/20 dark:text-red-100">
                            {t("orders.modals.supplier.mapping.missing")}
                          </span>
                        )}
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td className="px-3 py-4 text-sm" colSpan={6} style={{ color: "var(--muted)" }}>
                        {isLoading ? t("loading") : t("orders.modals.supplier.empty")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="mt-3 rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="text-sm font-semibold">{t("orders.modals.supplier.payloadTitle")}</p>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.supplier.payloadSubtitle")}</p>
            <div className="mt-2 max-h-28 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              {payloadProducts.length ? payloadProducts.map((row) => (
                <p key={`${row.id}-${row.count}`} className="font-mono text-xs">
                  {`{ id: ${row.id}, count: ${row.count} }`}
                </p>
              )) : (
                <p className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.supplier.payloadEmpty")}</p>
              )}
            </div>
            {preview && !preview.can_submit ? (
              <p className="mt-2 text-xs text-red-700 dark:text-red-200">
                {t("orders.modals.supplier.cannotSubmit", { count: preview.missing_count })}
              </p>
            ) : null}
            {preview?.last_supplier_order_id ? (
              <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                {t("orders.modals.supplier.lastOrder", { id: preview.last_supplier_order_id })}
              </p>
            ) : null}
          </section>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={onClose}
              disabled={isSubmitting || isCancelling}
            >
              {t("orders.actions.close")}
            </button>
            {preview?.last_supplier_order_id ? (
              <button
                type="button"
                className="h-9 rounded-md border border-red-500/55 bg-red-500/12 px-3 text-xs font-semibold text-red-700 transition-colors hover:bg-red-500/20 disabled:opacity-60 dark:border-red-300/70 dark:bg-red-500/30 dark:text-red-100 dark:hover:bg-red-500/40"
                onClick={onCancelSupplierOrder}
                disabled={isSubmitting || isCancelling}
              >
                {isCancelling ? t("loading") : t("orders.modals.supplier.actions.cancelSupplierOrder")}
              </button>
            ) : null}
          </div>

          <button
            type="button"
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={!canSubmit || isSubmitting || isCancelling}
            onClick={onSubmit}
          >
            {isSubmitting ? t("loading") : t("orders.modals.supplier.actions.submit")}
          </button>
        </footer>
      </div>
    </div>
  );
}
