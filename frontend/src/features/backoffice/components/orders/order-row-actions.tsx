import { Eye, ReceiptText, Trash2, Truck, type LucideIcon } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function ActionIconButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  tone = "default",
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
}) {
  const isDanger = tone === "danger";

  return (
    <BackofficeTooltip
      content={label}
      placement="top"
      align="center"
      wrapperClassName="inline-flex"
      tooltipClassName="whitespace-nowrap"
    >
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
        style={{
          borderColor: isDanger ? "#ef4444" : "var(--border)",
          backgroundColor: "var(--surface)",
          color: isDanger ? "#dc2626" : "var(--text)",
        }}
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
      >
        <Icon className="h-4 w-4" />
      </button>
    </BackofficeTooltip>
  );
}

export function OrderRowActions({
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
  return (
    <div className="flex items-center gap-1.5 whitespace-nowrap">
      <ActionIconButton
        label={opening ? t("loading") : t("orders.tooltips.open")}
        icon={Eye}
        disabled={opening}
        onClick={onOpen}
      />
      <ActionIconButton
        label={processingWaybill ? t("loading") : t("orders.tooltips.waybill")}
        icon={ReceiptText}
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
