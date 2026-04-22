"use client";

import type { LucideIcon } from "lucide-react";
import { CheckCircle2, CircleHelp, Clock3, LoaderCircle, MinusCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { normalizeStatusKey, normalizeStatusLabel } from "@/features/backoffice/lib/status";
import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";

function resolveSupportTone(statusKey: string): BackofficeStatusChipTone {
  if (statusKey === "new") {
    return "info";
  }
  if (statusKey === "open") {
    return "blue";
  }
  if (statusKey === "resolved") {
    return "success";
  }
  if (statusKey === "closed") {
    return "gray";
  }
  if (statusKey === "waiting_for_support") {
    return "warning";
  }
  if (statusKey === "waiting_for_client") {
    return "info";
  }
  return "gray";
}

function resolveSupportIcon(statusKey: string): LucideIcon {
  if (statusKey === "new") {
    return Clock3;
  }
  if (statusKey === "open") {
    return LoaderCircle;
  }
  if (statusKey === "resolved") {
    return CheckCircle2;
  }
  if (statusKey === "closed") {
    return MinusCircle;
  }
  if (statusKey === "waiting_for_support" || statusKey === "waiting_for_client") {
    return Clock3;
  }
  return CircleHelp;
}

export function SupportStatusChip({ status }: { status: string }) {
  const t = useTranslations("backoffice.common");
  const key = normalizeStatusKey(status);
  let label = normalizeStatusLabel(status) || t("statuses.unknown");
  try {
    label = t(`statuses.${key}`);
  } catch {
    label = normalizeStatusLabel(status) || t("statuses.unknown");
  }

  return (
    <BackofficeStatusChip tone={resolveSupportTone(key)} icon={resolveSupportIcon(key)}>
      {label}
    </BackofficeStatusChip>
  );
}
