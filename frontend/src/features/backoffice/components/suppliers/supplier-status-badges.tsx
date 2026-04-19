import { Timer } from "lucide-react";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { supplierToneIcon, type SupplierStatusTone } from "@/features/backoffice/lib/suppliers/supplier-status";

export function SupplierTokenStateBadge({
  tone,
  label,
}: {
  tone: SupplierStatusTone;
  label: string;
}) {
  return (
    <BackofficeStatusChip tone={tone} icon={supplierToneIcon(tone)}>
      {label}
    </BackofficeStatusChip>
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
    <BackofficeStatusChip tone={tone} icon={Timer} palette="countdown">
      {label}
    </BackofficeStatusChip>
  );
}
