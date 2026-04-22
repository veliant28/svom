import { getJson } from "@/shared/api/http-client";

import type { BackofficeStaffActivityPayload, BackofficeStaffActivityRole, BackofficeSummary } from "@/features/backoffice/types/backoffice";

export async function getBackofficeSummary(token: string): Promise<BackofficeSummary> {
  return getJson<BackofficeSummary>("/backoffice/summary/", undefined, { token });
}

export async function getBackofficeStaffActivity(
  token: string,
  params: { role: BackofficeStaffActivityRole; days?: number },
): Promise<BackofficeStaffActivityPayload> {
  const query = new URLSearchParams();
  query.set("role", params.role);
  if (typeof params.days === "number" && Number.isFinite(params.days)) {
    query.set("days", String(Math.max(1, Math.floor(params.days))));
  }
  return getJson<BackofficeStaffActivityPayload>(`/backoffice/summary/staff/?${query.toString()}`, undefined, { token });
}
