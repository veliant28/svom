import type { LucideIcon } from "lucide-react";
import { CheckCircle2, CircleHelp, Clock3, LoaderCircle, PackageCheck, Truck, XCircle } from "lucide-react";
import type { BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";

export function formatMoney(value: string, currency: string, locale: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return `${value} ${currency}`;
  }

  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount) + ` ${currency}`;
}

export function formatDateTime(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function resolveOrderStatusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "completed" || status === "shipped" || status === "ready_for_shipment") {
    return "success";
  }
  if (status === "cancelled") {
    return "danger";
  }
  if (status === "processing") {
    return "warning";
  }
  return "neutral";
}

export function resolveOrderStatusChipTone(status: string): BackofficeStatusChipTone {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "new") {
    return "info";
  }
  if (normalized === "processing") {
    return "blue";
  }
  if (normalized === "ready_for_shipment" || normalized === "ready_to_ship") {
    return "orange";
  }
  if (normalized === "shipped") {
    return "brown";
  }
  if (normalized === "completed") {
    return "success";
  }
  if (normalized === "cancelled") {
    return "error";
  }
  return "info";
}

export function resolveOrderStatusChipIcon(status: string): LucideIcon {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "new") {
    return Clock3;
  }
  if (normalized === "processing") {
    return LoaderCircle;
  }
  if (normalized === "ready_for_shipment" || normalized === "ready_to_ship") {
    return PackageCheck;
  }
  if (normalized === "shipped") {
    return Truck;
  }
  if (normalized === "completed") {
    return CheckCircle2;
  }
  if (normalized === "cancelled") {
    return XCircle;
  }
  return CircleHelp;
}
