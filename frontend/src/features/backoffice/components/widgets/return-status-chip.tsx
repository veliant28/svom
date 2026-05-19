"use client";

import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Banknote,
  CheckCircle2,
  Clock3,
  Package,
  Truck,
  XCircle,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { ReturnStatus } from "@/features/commerce/types";

type ReturnStatusMeta = {
  tone: BackofficeStatusChipTone;
  icon: LucideIcon;
};

const RETURN_STATUS_META: Record<ReturnStatus, ReturnStatusMeta> = {
  new: { tone: "info", icon: Clock3 },
  approved: { tone: "success", icon: CheckCircle2 },
  rejected: { tone: "error", icon: XCircle },
  awaiting_ttn: { tone: "warning", icon: AlertTriangle },
  in_transit: { tone: "blue", icon: Truck },
  received: { tone: "success", icon: CheckCircle2 },
  accepted: { tone: "success", icon: CheckCircle2 },
  refunded: { tone: "black", icon: Banknote },
  cancelled: { tone: "gray", icon: Package },
};

function normalizeReturnStatus(status: string): ReturnStatus {
  const key = String(status || "").trim().toLowerCase() as ReturnStatus;
  if (key in RETURN_STATUS_META) {
    return key;
  }
  return "new";
}

export function ReturnStatusChip({ status, className = "" }: { status: string; className?: string }) {
  const tStatuses = useTranslations("backoffice.common.statuses");
  const normalized = normalizeReturnStatus(status);
  const meta = RETURN_STATUS_META[normalized];
  const labelKey =
    normalized === "received"
      ? "accepted"
      : normalized === "refunded"
        ? "refund"
        : normalized === "awaiting_ttn"
          ? "no_ttn"
          : normalized;
  const label = tStatuses(labelKey);

  return (
    <BackofficeStatusChip tone={meta.tone} icon={meta.icon} className={className}>
      {label}
    </BackofficeStatusChip>
  );
}
