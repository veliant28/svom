import { ScanBarcode, ScanLine, X } from "lucide-react";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { Translator } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type { BackofficeOrderNovaPoshtaWaybill } from "@/features/backoffice/types/nova-poshta.types";

export function OrderWaybillModalHeader({
  waybill,
  t,
  onClose,
}: {
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  t: Translator;
  onClose: () => void;
}) {
  return (
    <header className="border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">{t("orders.modals.waybill.title")}</h2>
          <BackofficeStatusChip
            tone={waybill?.np_number ? "success" : "orange"}
            icon={waybill?.np_number ? ScanBarcode : ScanLine}
            className="h-7 px-2 py-0 tracking-wide"
          >
            {waybill?.np_number || t("orders.table.waybillEmpty")}
          </BackofficeStatusChip>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            aria-label={t("orders.actions.closeModal")}
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
