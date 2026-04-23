import { getJson } from "@/shared/api/http-client";

import type { PromoBannerConfig } from "@/features/marketing/types";

export async function getPromoBannerConfig(locale: string): Promise<PromoBannerConfig> {
  return getJson<PromoBannerConfig>("/marketing/promo-banners/config/", { lang: locale });
}
