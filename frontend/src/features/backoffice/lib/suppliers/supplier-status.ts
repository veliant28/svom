import type { LucideIcon } from "lucide-react";
import { CheckCircle2, CircleAlert, Plug, XCircle } from "lucide-react";

import { normalizeStatusKey } from "@/features/backoffice/lib/status";

export type SupplierStatusTone = "success" | "warning" | "error" | "info";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function supplierTokenCountdownTone(secondsLeft: number | null, warningThresholdSeconds = 15 * 60): SupplierStatusTone {
  if (secondsLeft === null) {
    return "info";
  }
  if (secondsLeft <= 0) {
    return "error";
  }
  if (secondsLeft <= warningThresholdSeconds) {
    return "warning";
  }
  return "success";
}

export function supplierToneIcon(tone: SupplierStatusTone): LucideIcon {
  if (tone === "success") {
    return CheckCircle2;
  }
  if (tone === "warning") {
    return CircleAlert;
  }
  if (tone === "error") {
    return XCircle;
  }
  return Plug;
}

export function supplierToneStatusKey(tone: SupplierStatusTone): string {
  if (tone === "success") {
    return "active";
  }
  if (tone === "warning") {
    return "attention";
  }
  if (tone === "error") {
    return "expired";
  }
  return "unknown";
}

export function resolveSupplierConnectionLabel(status: string | null | undefined, tCommon: Translator): string {
  if (!status) {
    return tCommon("statuses.unknown");
  }

  const key = normalizeStatusKey(status);
  try {
    return tCommon(`statuses.${key}`);
  } catch {
    return tCommon("statuses.unknown");
  }
}

export function resolveSupplierTokenStateLabel(tone: SupplierStatusTone, tCommon: Translator): string {
  const key = supplierToneStatusKey(tone);
  try {
    return tCommon(`statuses.${key}`);
  } catch {
    return tCommon("statuses.unknown");
  }
}
