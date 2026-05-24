import { Timer } from "lucide-react";

import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { supplierToneIcon, type SupplierStatusTone } from "@/features/backoffice/lib/suppliers/supplier-status";

export function SupplierTokenStateBadge({
  tone,
  label,
}: {
  tone: SupplierStatusTone;
  label: string;
}) {
  return (
    <StatusChip tone={tone} icon={supplierToneIcon(tone)}>
      {label}
    </StatusChip>
  );
}

export function SupplierTokenCountdownBadge({
  tone,
  label,
}: {
  tone: SupplierStatusTone;
  label: string;
}) {
  return (
    <StatusChip tone={tone} icon={Timer} palette="countdown">
      {label}
    </StatusChip>
  );
}
