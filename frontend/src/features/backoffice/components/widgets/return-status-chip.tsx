"use client";

import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  Package,
  PackageCheck,
  RefreshCw,
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
  received: { tone: "teal", icon: PackageCheck },
  accepted: { tone: "success", icon: CheckCircle2 },
  refund_processing: { tone: "orange", icon: RefreshCw },
  refunded: { tone: "success", icon: BadgeCheck },
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
  const label = tStatuses(normalized);

  return (
    <BackofficeStatusChip tone={meta.tone} icon={meta.icon} className={className}>
      {label}
    </BackofficeStatusChip>
  );
}
