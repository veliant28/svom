import { Eye, ScanBarcode, ScanLine, Trash2, Truck } from "lucide-react";

import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrderRowActions({
  hasWaybill,
  deleting,
  opening,
  processingWaybill,
  processingSupplier,
  onOpen,
  onWaybill,
  onSupplierOrder,
  onDelete,
  t,
}: {
  hasWaybill: boolean;
  deleting: boolean;
  opening: boolean;
  processingWaybill: boolean;
  processingSupplier: boolean;
  onOpen: () => void;
  onWaybill: () => void;
  onSupplierOrder: () => void;
  onDelete: () => void;
  t: Translator;
}) {
  const waybillLabel = processingWaybill
    ? t("loading")
    : hasWaybill
      ? t("orders.tooltips.waybill")
      : t("orders.tooltips.waybillCreate");

  return (
    <div className="flex items-center gap-1.5 whitespace-nowrap">
      <ActionIconButton
        label={opening ? t("loading") : t("orders.tooltips.open")}
        icon={Eye}
        disabled={opening}
        onClick={onOpen}
      />
      <ActionIconButton
        label={waybillLabel}
        icon={hasWaybill ? ScanBarcode : ScanLine}
        disabled={processingWaybill}
        onClick={onWaybill}
      />
      <ActionIconButton
        label={processingSupplier ? t("loading") : t("orders.tooltips.supplierOrder")}
        icon={Truck}
        disabled={processingSupplier}
        onClick={onSupplierOrder}
      />
      <ActionIconButton
        label={deleting ? t("loading") : t("orders.tooltips.delete")}
        icon={Trash2}
        tone="danger"
        disabled={deleting}
        onClick={onDelete}
      />
    </div>
  );
}
