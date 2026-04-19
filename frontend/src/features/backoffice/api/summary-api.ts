import { getJson } from "@/shared/api/http-client";

import type { BackofficeSummary } from "@/features/backoffice/types/backoffice";

export async function getBackofficeSummary(token: string): Promise<BackofficeSummary> {
  return getJson<BackofficeSummary>("/backoffice/summary/", undefined, { token });
}
