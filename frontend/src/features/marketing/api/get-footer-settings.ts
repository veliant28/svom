import { getJson } from "@/shared/api/http-client";

import type { MarketingFooterSettings } from "@/features/marketing/types";

export async function getFooterSettings(): Promise<MarketingFooterSettings> {
  return getJson<MarketingFooterSettings>("/marketing/footer-settings/");
}
