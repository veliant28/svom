import type { BackofficeImportSource } from "@/features/backoffice/types/imports.types";

export function shouldShowSupplierFingerprint(activeCode: string): boolean {
  return activeCode === "utr";
}

export function buildSupplierSettingsPayload({
  login,
  password,
  fingerprint,
  isEnabled,
}: {
  login: string;
  password: string;
  fingerprint: string;
  isEnabled: boolean;
}) {
  return {
    login,
    password: password || undefined,
    browser_fingerprint: fingerprint || undefined,
    is_enabled: isEnabled,
  };
}

export function buildDefaultImportSchedulePayload(item: BackofficeImportSource) {
  return {
    schedule_cron: item.schedule_cron || "*/30 * * * *",
    schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
    auto_reprice_after_import: item.auto_reprice_after_import,
    auto_reindex_after_import: item.auto_reindex_after_import,
  };
}
