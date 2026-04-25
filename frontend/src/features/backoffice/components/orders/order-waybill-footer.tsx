import type { Translator } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeOrderNovaPoshtaWaybill } from "@/features/backoffice/types/nova-poshta.types";

export function OrderWaybillFooter({
  waybill,
  isBusy,
  isSubmitting,
  canSubmit,
  isReadonlyDocument,
  payloadForSave,
  t,
  onDelete,
  onRefresh,
  onTrack,
  onPrint,
  onSave,
}: {
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  isBusy: boolean;
  isSubmitting: boolean;
  canSubmit: boolean;
  isReadonlyDocument: boolean;
  payloadForSave: WaybillFormPayload;
  t: Translator;
  onDelete: () => void;
  onRefresh: () => void;
  onTrack: () => void;
  onPrint: (format: "html" | "pdf") => void;
  onSave: (payload: WaybillFormPayload) => void;
}) {
  return (
    <footer className="border-t px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1">
          {waybill ? (
            <button
              type="button"
              className="h-10 rounded-md border px-4 text-xs font-semibold"
              style={{ borderColor: "#dc2626", backgroundColor: "#dc2626", color: "#fff" }}
              disabled={isBusy}
              onClick={onDelete}
            >
              {t("orders.modals.waybill.actions.delete")}
            </button>
          ) : null}

          <button
            type="button"
            className="h-10 rounded-md border px-4 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={isBusy || !waybill}
            onClick={onRefresh}
          >
            {t("orders.modals.waybill.actions.checkReaddress")}
          </button>
          <button
            type="button"
            className="h-10 rounded-md border px-4 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={isBusy || !waybill}
            onClick={onRefresh}
          >
            {t("orders.modals.waybill.actions.checkReturn")}
          </button>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-1">
          <button
            type="button"
            className="h-10 rounded-md border px-4 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={isBusy || !waybill}
            onClick={onTrack}
          >
            {t("orders.modals.waybill.actions.trackTtn")}
          </button>
          <button
            type="button"
            className="h-10 rounded-md border px-4 text-xs font-semibold"
            style={{ borderColor: "#d4d4d8", backgroundColor: "#f4f4f5", color: "#3f3f46" }}
            disabled={isBusy || !waybill}
            onClick={() => onPrint("html")}
          >
            {t("orders.modals.waybill.actions.printHtml")}
          </button>
          <button
            type="button"
            className="h-10 rounded-md border px-4 text-xs font-semibold"
            style={{ borderColor: "#52525b", backgroundColor: "#52525b", color: "#fafafa" }}
            disabled={isBusy || !waybill}
            onClick={() => onPrint("pdf")}
          >
            {t("orders.modals.waybill.actions.printPdf")}
          </button>
          <button
            type="button"
            className="h-10 rounded-md border px-4 text-xs font-semibold"
            style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            disabled={!canSubmit}
            onClick={() => onSave(payloadForSave)}
            title={isReadonlyDocument ? t("orders.modals.waybill.meta.readonlyHint") : undefined}
          >
            {isSubmitting ? t("loading") : waybill ? t("orders.modals.waybill.actions.update") : t("orders.modals.waybill.actions.create")}
          </button>
        </div>
      </div>
    </footer>
  );
}
